"""
Live video-analysis pipeline manager.

Owns, for each active site, ONE background processing loop that reads frames
from a :class:`VideoSource`, runs real YOLO detection, computes detection-derived
safety stats and an explainable risk score (with a rolling window), emits
debounced safety events, keeps the latest annotated JPEG for the MJPEG stream,
and broadcasts JSON snapshots to WebSocket subscribers.

Design goals:
  * one pipeline per site/source (not one per browser connection)
  * YOLO model loaded once, reused (see ai.computer_vision.ppe_detector)
  * never fabricates data; on any error the pipeline surfaces a clear status
"""

from __future__ import annotations

import asyncio
import io
import logging
import queue
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

import cv2

from .risk_engine import LiveRiskEngine
from .event_processor import SafetyEventProcessor
from .video_source import VideoSource

logger = logging.getLogger(__name__)

# Inference/annotation/config defaults (override via env, see pipeline config).
DEFAULT_CONF = 0.45
DEFAULT_DETECTION_INTERVAL = 0.5   # ~2 inference batches / second
DEFAULT_RENDER_INTERVAL = 0.25     # MJPEG frame rate cap
DEFAULT_PROCESS_WIDTH = 1280       # downscale before inference for speed
# Minimum gap between source-frame decodes (~10 fps decode cap) so we don't
# burn CPU decoding the full-res video between detection/render ticks.
MIN_FRAME_GAP = 0.1


class LivePipeline:
    """A single site's live video analysis."""

    def __init__(
        self,
        site_id: str,
        video_source: str | int,
        model_path: Optional[str] = None,
        conf: float = DEFAULT_CONF,
        process_width: int = DEFAULT_PROCESS_WIDTH,
        detection_interval: float = DEFAULT_DETECTION_INTERVAL,
    ) -> None:
        self.site_id = site_id
        self.source = video_source
        self.conf = conf
        self.process_width = int(process_width)
        self.detection_interval = float(detection_interval)

        self.risk = LiveRiskEngine()
        self.events = SafetyEventProcessor()

        self._source = VideoSource(video_source)
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._lock = threading.Lock()

        self.status = "STOPPED"          # STOPPED | STARTING | LIVE | STREAM_ENDED | ERROR
        self.status_detail: str = ""
        self.last_detection_at: Optional[str] = None
        self.started_at: Optional[str] = None

        self._latest_snapshot: Dict[str, Any] = {}
        self._latest_jpeg: Optional[bytes] = None
        self._annotated_dims: tuple = (0, 0)

        # Detector singletons (cached, loaded once).
        self._base = None
        self._ppe = None
        self.model_path = model_path

    # ── subscribers ─────────────────────────────────────────────────────
    def _subscribers(self):
        return _SUBSCRIBERS.setdefault(self.site_id, set())

    def subscribe(self, q: queue.Queue) -> None:
        with _SUBS_LOCK:
            self._subscribers().add(q)
        # Immediately deliver the latest snapshot if we have one.
        with self._lock:
            snap = dict(self._latest_snapshot)
        if snap:
            q.put_nowait(snap)

    def unsubscribe(self, q: queue.Queue) -> None:
        with _SUBS_LOCK:
            self._subscribers().discard(q)

    def _broadcast(self, snapshot: Dict[str, Any]) -> None:
        with _SUBS_LOCK:
            subs = list(self._subscribers())
        for q in subs:
            try:
                q.put_nowait(snapshot)
            except queue.Full:
                pass

    # ── control ─────────────────────────────────────────────────────────
    def start(self) -> Dict[str, Any]:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return {"status": self.status, "detail": "Already running"}
            self._stop.clear()
            self.risk.reset()
            self.events.reset()
            self.status = "STARTING"
            self.started_at = datetime.now(timezone.utc).isoformat()
            self.last_detection_at = None
            self._thread = threading.Thread(
                target=self._run, name=f"live-{self.site_id}", daemon=True
            )
            self._thread.start()
        logger.info("Live analysis started for site %s", self.site_id)
        return {"status": self.status, "detail": "started"}

    def stop(self) -> Dict[str, Any]:
        self._stop.set()
        self._source.close()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        with self._lock:
            self.status = "STOPPED"
            self.status_detail = ""
        # Broadcast the terminal state so WebSocket subscribers stop receiving
        # the stale LIVE metrics snapshot and can settle on STOPPED.
        self._broadcast(self._build_status_snapshot())
        logger.info("Live analysis stopped for site %s", self.site_id)
        return {"status": "STOPPED", "detail": "stopped"}

    def close(self) -> None:
        self.stop()

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # ── detectors (lazy, cached) ────────────────────────────────────────
    def _get_detectors(self):
        from ai.computer_vision.detector import ConstructionSiteDetector
        from ai.computer_vision.ppe_detector import get_ppe_detector, PPEModelUnavailable

        if self._base is None:
            self._base = ConstructionSiteDetector(conf=self.conf)
        if self._ppe is None:
            self._ppe = get_ppe_detector()
        return self._base, self._ppe

    # ── snapshots ───────────────────────────────────────────────────────
    @property
    def latest_snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._latest_snapshot)

    @property
    def latest_jpeg(self) -> Optional[bytes]:
        with self._lock:
            return self._latest_jpeg

    # ── main loop ───────────────────────────────────────────────────────
    def _run(self) -> None:
        try:
            self._loop_body()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Live pipeline error for site %s", self.site_id)
            with self._lock:
                self.status = "ERROR"
                self.status_detail = str(exc)
            self._broadcast(self._build_status_snapshot())
        finally:
            self._source.close()

    def _loop_body(self) -> None:
        base, ppe = self._get_detectors()
        if not ppe.available:
            raise RuntimeError("PPE model unavailable; cannot start live analysis")

        self._source.open()
        with self._lock:
            self.status = "LIVE"
            self.status_detail = "Processing"

        last_detect = 0.0
        last_render = 0.0
        _last_loop = 0.0
        idle_frames = 0

        while not self._stop.is_set():
            now = time.monotonic()
            if now - _last_loop < MIN_FRAME_GAP:
                # Cap frame decode churn so we aren't chewing CPU decoding the
                # full-resolution source between detection/render ticks.
                time.sleep(MIN_FRAME_GAP - (now - _last_loop))
            _last_loop = time.monotonic()

            ok, frame = self._source.read()
            if not ok or frame is None:
                idle_frames += 1
                # Let a file loop poll briefly so we can still stop cleanly.
                time.sleep(0.2)
                if idle_frames >= 2:
                    self._finish_stream_ended()
                    return
                continue
            idle_frames = 0

            now = time.monotonic()
            if now - last_detect >= self.detection_interval:
                last_detect = now
                snapshot = self._process_frame(base, ppe, frame)
                with self._lock:
                    self._latest_snapshot = snapshot
                self._broadcast(snapshot)

            # Update annotated video at a bounded rate.
            h, w = frame.shape[:2]
            now_r = time.monotonic()
            if now_r - last_render >= DEFAULT_RENDER_INTERVAL:
                last_render = now_r
                annotated = self._annotate(frame, snapshot)
                # Downscale before encoding so the MJPEG stream doesn't pay the
                # full cost of JPEG-encoding a 4K frame every tick.
                ah, aw = annotated.shape[:2]
                if aw > self.process_width:
                    s = self.process_width / aw
                    annotated = cv2.resize(
                        annotated,
                        (self.process_width, int(round(ah * s))),
                        interpolation=cv2.INTER_AREA,
                    )
                jpeg_bytes = cv2.imencode(
                    ".jpg", annotated, [int(cv2.IMWRITE_JPEG_QUALITY), 75]
                )[1].tobytes()
                with self._lock:
                    self._latest_jpeg = jpeg_bytes
                    self._annotated_dims = (w, h)

    def _finish_stream_ended(self) -> None:
        with self._lock:
            self.status = "STREAM_ENDED"
            self.status_detail = "Video source ended"
        self._broadcast(self._build_status_snapshot())
        logger.info("Video source ended for site %s", self.site_id)

    # ── inference + stats ──────────────────────────────────────────────
    def _process_frame(self, base, ppe, frame) -> Dict[str, Any]:
        # Downscale for inference performance (pipeline-local; annotations use
        # the original frame with bbox scaling).
        work = frame
        scale = 1.0
        if self.process_width and frame.shape[1] > self.process_width:
            scale = self.process_width / frame.shape[1]
            work = cv2.resize(
                frame,
                (self.process_width, int(frame.shape[0] * scale)),
            )

        base_dets = base.detect_from_frame(work)
        persons = [d for d in base_dets if d.get("class_id") == 0]
        # Person anchors stay in the SAME (resized) coordinate space as `work`
        # so PPE boxes from analyze_workers/infer overlap them correctly.
        person_boxes = [
            {"bbox": list(d["bbox"]), "confidence": d.get("confidence", 0.9)}
            for d in persons
        ]

        ppe_result = ppe.analyze_workers(work, person_detections=person_boxes)
        workers = ppe_result.get("workers", [])

        # Cross-scale PPE inference too (relative to the resized frame) then
        # rescale boxes to original for annotation.
        ppe_infer = ppe.infer(work)
        raw_dets = list(ppe_infer["detections"])
        ppe_dets = []
        for d in raw_dets:
            d = dict(d)
            d["bbox"] = [v / scale for v in d["bbox"]]
            ppe_dets.append(d)

        # Aggregate detection-derived stats.
        non_compliant = [w for w in workers if w["ppe_status"] != "compliant"]
        helmet_violations = sum(
            1 for w in non_compliant if "helmet" in (w.get("missing_ppe") or [])
        )
        vest_violations = sum(
            1 for w in non_compliant if "vest" in (w.get("missing_ppe") or [])
        )
        other_violations = sum(
            1
            for w in non_compliant
            if not any(x in (w.get("missing_ppe") or []) for x in ("helmet", "vest"))
        )

        risk = self.risk.add_observation(
            workers=len(workers),
            helmet_violations=helmet_violations,
            vest_violations=vest_violations,
            other_violations=other_violations,
        )
        new_events = self.events.process(workers)
        self._maybe_persist(workers, risk, new_events)

        ts = datetime.now(timezone.utc).isoformat()
        self.last_detection_at = ts

        return {
            "type": "metrics",
            "status": "LIVE",
            "site_id": self.site_id,
            "timestamp": ts,
            "last_detection": ts,
            "frame_index": 0,
            "workers": len(workers),
            "helmet_violations": helmet_violations,
            "vest_violations": vest_violations,
            "other_violations": other_violations,
            "total_violations": risk["total_violations"],
            "ppe_compliance": risk["ppe_compliance"],
            "risk_score": risk["risk_score"],
            "risk_level": risk["risk_level"],
            "reasons": risk["reasons"],
            "detections": ppe_dets,
            "base_detections": [
                {"label": d.get("label"), "bbox": list(d.get("bbox", [])), "confidence": d.get("confidence")}
                for d in base_dets
            ],
            "events": new_events,
        }

    def _annotate(self, frame, snapshot) -> Any:
        if not snapshot:
            return frame
        detections = snapshot.get("detections", [])
        for d in detections:
            bbox = d.get("bbox")
            if not bbox or len(bbox) != 4:
                continue
            x1, y1, x2, y2 = [int(v) for v in bbox]
            name = d.get("class_name", d.get("label", "?"))
            color = (
                (0, 0, 255)
                if "no_" in name or name in ("none",)
                else (255, 165, 0)
            )
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(
                frame,
                f"{name} {d.get('confidence', 0):.2f}",
                (x1, max(12, y1 - 6)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                2,
                cv2.LINE_AA,
            )
        return frame

    def _build_status_snapshot(self) -> Dict[str, Any]:
        return {
            "type": "metrics",
            "status": self.status,
            "site_id": self.site_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "detail": self.status_detail,
        }

    # ── optional lightweight persistence ───────────────────────────────
    def _maybe_persist(self, workers, risk, new_events) -> None:
        # Persist is best-effort and rate-limited by new_events only; keeping
        # every inference window out of the DB. High-frequency live state stays
        # in memory. Real detection events are reflected in WS + status.
        try:
            if new_events:
                self._persist_events(new_events, risk)
        except Exception as exc:  # noqa: BLE001
            logger.debug("event persistence skipped: %s", exc)

    def _persist_events(self, new_events, risk) -> None:
        from app.database.database import SessionLocal
        from app.models.models import SafetyViolation

        db = SessionLocal()
        try:
            for ev in new_events:
                if ev["event_type"] == "PPE_COMPLIANT":
                    continue
                db.add(
                    SafetyViolation(
                        site_id=self.site_id,
                        violation_type=ev["event_type"].lower(),
                        description=ev["message"],
                        severity=ev["severity"],
                        risk_contribution=18.0,
                        recommended_mitigation="Enforce PPE compliance for affected worker(s)",
                        status="open",
                        source="live_video",
                        timestamp=datetime.now(timezone.utc),
                    )
                )
            db.commit()
        except Exception:  # noqa: BLE001
            db.rollback()
        finally:
            db.close()


# ── registry (one pipeline per site) + subscriber bookkeeping ────────────────
_PIPELINES: Dict[str, LivePipeline] = {}
_PIPELINE_LOCK = threading.Lock()
_SUBSCRIBERS: Dict[str, Set[queue.Queue]] = {}
_SUBS_LOCK = threading.Lock()


class LiveManager:
    """Registry of live pipelines and helper to broadcast to subscribers."""

    @staticmethod
    def get_or_create(site_id: str, video_source, **kwargs) -> LivePipeline:
        with _PIPELINE_LOCK:
            pipe = _PIPELINES.get(site_id)
            if pipe is None:
                pipe = LivePipeline(site_id, video_source, **kwargs)
                _PIPELINES[site_id] = pipe
        return pipe

    @staticmethod
    def get(site_id: str) -> Optional[LivePipeline]:
        with _PIPELINE_LOCK:
            return _PIPELINES.get(site_id)

    @staticmethod
    def start(site_id: str, video_source, **kwargs):
        pipe = LiveManager.get_or_create(site_id, video_source, **kwargs)
        return pipe.start()

    @staticmethod
    def stop(site_id: str):
        pipe = LiveManager.get(site_id)
        if pipe:
            return pipe.stop()
        return {"status": "STOPPED", "detail": "not running"}

    @staticmethod
    def status(site_id: str) -> Dict[str, Any]:
        pipe = LiveManager.get(site_id)
        if pipe is None:
            return {
                "status": "STOPPED",
                "site_id": site_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "detail": "No pipeline configured",
            }
        with pipe._lock:
            base = {
                "site_id": site_id,
                "status": pipe.status,
                "detail": pipe.status_detail,
                "started_at": pipe.started_at,
                "last_detection": pipe.last_detection_at,
                "source": str(pipe.source),
            }
            if pipe._latest_snapshot:
                snap = dict(pipe._latest_snapshot)
                for k in ("type", "event_id"):
                    base.pop(k, None)
                base.update(
                    {
                        "workers": snap.get("workers"),
                        "helmet_violations": snap.get("helmet_violations"),
                        "vest_violations": snap.get("vest_violations"),
                        "other_violations": snap.get("other_violations"),
                        "total_violations": snap.get("total_violations"),
                        "ppe_compliance": snap.get("ppe_compliance"),
                        "risk_score": snap.get("risk_score"),
                        "risk_level": snap.get("risk_level"),
                        "reasons": snap.get("reasons"),
                    }
                )
            return base

    @staticmethod
    def shutdown() -> None:
        with _PIPELINE_LOCK:
            for pipe in list(_PIPELINES.values()):
                pipe.close()


manager = LiveManager()
