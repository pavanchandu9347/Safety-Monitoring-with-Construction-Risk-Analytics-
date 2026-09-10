"""
Shared real-video analysis service.

Runs real YOLO detection (base construction objects + PPE) over the SAME
configured video source used by the live pipeline and caches an aggregated
report. Every module's "analyze" endpoint consumes this report, so risk,
safety, monitoring and demo scores all trace back to the same real footage
instead of hardcoded constants.

Real-detection only: this module never fabricates objects or workers. If a
source cannot be opened, the report carries an ``error`` and empty lists, and
the downstream agents simply score "nothing detected".
"""

from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.config import (
    CONFIDENCE_THRESHOLD,
    FRAME_SAMPLE_RATE,
    MAX_FRAMES,
    PROCESS_WIDTH,
    default_video_source,
)

logger = logging.getLogger(__name__)


def _box_key(box: List[float]) -> str:
    return f"{float(box[0]):.1f},{float(box[1]):.1f},{float(box[2]):.1f},{float(box[3]):.1f}"


class _WorkerTracker:
    """Lightweight IoU-based association of person detections across frames.

    Sample frames can be seconds apart, so matching uses a generous overlap
    floor plus a centre-distance guard. A worker reappearing after a long gap
    (larger than ``_MAX_REASSOC_FRAMES`` sampled frames) is treated as a new
    observation — honest behaviour rather than a fabricated identity.
    """

    _MAX_REASSOC = 4  # max sampled-frames gap before a worker is considered new

    def __init__(self) -> None:
        self._workers: Dict[str, Dict[str, Any]] = {}

    def observe(self, worker: Dict[str, Any], frame_index: int, fps: float) -> str:
        box = worker.get("bbox")
        if not box or len(box) < 4:
            return ""
        box = [float(v) for v in box[:4]]
        best_id: Optional[str] = None
        best_iou = 0.0
        for wid, rec in self._workers.items():
            gap = frame_index - rec["last_frame"]
            if (gap / max(fps, 1.0)) > 3.0:
                continue
            iou = self._iou(box, rec["last_box"])
            if iou > best_iou:
                best_iou = iou
                best_id = wid

        if best_id is not None and best_iou >= 0.12:
            rec = self._workers[best_id]
        else:
            best_id = f"w-{len(self._workers) + 1}"
            rec = {
                "worker_id": best_id,
                "first_frame": frame_index,
                "last_frame": frame_index,
                "frames_seen": 0,
                "ppe_samples": [],
                "detected_ppe": set(),
                "missing_ppe": set(),
                "last_box": box,
                "bbox": box,
                "confidence": worker.get("confidence", 0.0),
            }
            self._workers[best_id] = rec

        rec["frames_seen"] += 1
        rec["last_frame"] = frame_index
        rec["last_box"] = box
        rec["bbox"] = box
        rec["confidence"] = max(float(rec.get("confidence") or 0.0), float(worker.get("confidence") or 0.0))
        status = worker.get("ppe_status", "insufficient_evidence")
        rec["ppe_samples"].append(status)
        rec["detected_ppe"].update(worker.get("detected_ppe", []))
        rec["missing_ppe"].update(worker.get("missing_ppe", []))
        return best_id

    def observe_many(
        self, workers: List[Dict[str, Any]], frame_index: int, fps: float
    ) -> Dict[str, str]:
        """Associate every worker in a frame with its tracked id (by bbox)."""
        assigned: Dict[str, str] = {}
        for wrk in workers:
            box = wrk.get("bbox")
            if not box or len(box) < 4:
                continue
            box = [float(v) for v in box[:4]]
            best_id = ""
            best_iou = 0.0
            for wid, rec in self._workers.items():
                if rec["last_frame"] != frame_index:
                    continue
                iou = self._iou(box, rec["last_box"])
                if iou > best_iou:
                    best_iou = iou
                    best_id = wid
            if best_iou >= 0.12:
                assigned[_box_key(box)] = best_id
                continue
            # Not seen this frame yet — run the regular association.
            clone = dict(wrk)
            assigned[_box_key(box)] = self.observe(clone, frame_index, fps)
        return assigned

    @staticmethod
    def _iou(a: List[float], b: List[float]) -> float:
        ax1, ay1, ax2, ay2 = a
        bx1, by1, bx2, by2 = b
        ix1, iy1, ix2, iy2 = max(ax1, bx1), max(ay1, by1), min(ax2, bx2), min(ay2, by2)
        inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
        if inter <= 0.0:
            return 0.0
        uni = (ax2 - ax1) * (ay2 - ay1) + (bx2 - bx1) * (by2 - by1) - inter
        return inter / uni if uni > 0 else 0.0

    def final_workers(self, fps: float, scale: float = 1.0) -> List[Dict[str, Any]]:
        final: List[Dict[str, Any]] = []
        for i, rec in enumerate(self._workers.values(), start=1):
            samples = rec["ppe_samples"]
            if "non_compliant" in samples:
                status = "non_compliant"
            elif "compliant" in samples:
                status = "compliant"
            else:
                status = "insufficient_evidence"
            final.append({
                "worker_id": rec["worker_id"],
                "worker_role": "worker",
                "first_frame": rec["first_frame"],
                "last_frame": rec["last_frame"],
                "frames_seen": rec["frames_seen"],
                "first_seen": round(rec["first_frame"] / max(fps, 1.0), 2),
                "last_seen": round(rec["last_frame"] / max(fps, 1.0), 2),
                "ppe_status": status,
                "detected_ppe": sorted(rec["detected_ppe"]),
                "missing_ppe": sorted(rec["missing_ppe"]),
                "confidence": round(float(rec.get("confidence") or 0.0), 3),
                "bbox": [round(float(v) / scale, 1) for v in rec["bbox"]],
            })
        return final

# The default video source is resolved to the construction-site video present in
# the project folder (env-driven via VIDEO_SOURCE). If several videos exist the
# caller passes an explicit path; the frontend exposes a selector.
DEFAULT_CONF: float = float(CONFIDENCE_THRESHOLD)

# Number of video frames to skip between analysis samples.
SAMPLE_INTERVAL: int = int(FRAME_SAMPLE_RATE)
# Maximum number of sampled frames analyzed per report.
MAX_SAMPLES: int = int(MAX_FRAMES)
# Downscale width before inference (matches the live pipeline).
PROCESS_WIDTH: int = int(PROCESS_WIDTH)
# Cache TTL (seconds) before the report is recomputed.
CACHE_TTL_SECONDS: float = 60.0

_report_cache: Dict[Any, Dict[str, Any]] = {}
_report_lock = threading.Lock()


def resolve_source(site_id: str = "", video_path: str = "") -> str | int:
    """Resolve the video source to analyze.

    Priority:
      1. an explicit ``video_path`` argument,
      2. the site's currently-running live pipeline source (the same video the
         dashboard is streaming right now),
      3. the project's construction-site video (auto-discovered; env override
         via ``VIDEO_SOURCE``).
    """
    if video_path:
        return video_path

    if site_id:
        try:
            from app.live.pipeline import manager

            pipe = manager.get(site_id)
            if pipe is not None and pipe.source is not None and pipe.status in ("LIVE", "STARTING"):
                return pipe.source
        except Exception as exc:  # noqa: BLE001
            logger.debug("Could not read live pipeline source: %s", exc)

    env = default_video_source()
    if isinstance(env, str) and env.strip().isdigit():
        return int(env.strip())
    return env


def get_video_report(
    site_id: str = "",
    video_path: str = "",
    conf: Optional[float] = None,
    force: bool = False,
) -> Dict[str, Any]:
    """Return the cached (or freshly computed) real video analysis report."""
    source = resolve_source(site_id=site_id, video_path=video_path)
    confidence = float(conf if conf is not None else DEFAULT_CONF)

    key = (str(source), round(confidence, 3), SAMPLE_INTERVAL, MAX_SAMPLES, PROCESS_WIDTH)
    now = time.monotonic()

    if not force:
        with _report_lock:
            cached = _report_cache.get(key)
        if cached is not None and now - cached.get("_computed_at", 0) < CACHE_TTL_SECONDS:
            return cached.copy()

    report = _compute_report(source, confidence)

    with _report_lock:
        cached = _report_cache.get(key)
        if cached is None or now - (cached.get("_computed_at") or 0) >= CACHE_TTL_SECONDS:
            report["_computed_at"] = now
            _report_cache[key] = report

    return report.copy()


def _open_capture(source: str | int):
    import cv2

    if isinstance(source, int):
        return cv2.VideoCapture(source)
    return cv2.VideoCapture(source)


def _compute_report(source: str | int, conf: float) -> Dict[str, Any]:
    from ai.computer_vision.detector import ConstructionSiteDetector
    from ai.computer_vision.ppe_detector import get_ppe_detector

    base = ConstructionSiteDetector(conf=conf)
    ppe = get_ppe_detector()

    report: Dict[str, Any] = {
        "source": str(source),
        "model_used": "yolov8n.pt",
        "worker_count": 0,
        "vehicle_count": 0,
        "helmet_violations": 0,
        "vest_violations": 0,
        "other_violations": 0,
        "total_violations": 0,
        "ppe_compliance": 100.0,
        "detected_objects": [],
        "ppe_workers": {
            "workers": [],
            "compliant_count": 0,
            "non_compliant_count": 0,
            "compliance_rate": 1.0,
            "total_workers": 0,
            "image_width": 0,
            "image_height": 0,
        },
        "frames_analyzed": 0,
        "lighting_condition": "",
        "frame_evidence": [],
        "error": "",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    capture = _open_capture(source)
    if capture is None or not capture.isOpened():
        report["error"] = f"Cannot open video source: {source}"
        logger.warning("Cannot open video source: %s", source)
        return report

    try:
        import cv2

        best_frame_dets: List[Dict] = []
        best_workers: List[Dict] = []
        best_ppe_meta: Dict[str, Any] = {}
        best_person_count = 0

        vehicle_max = 0
        workers_max = 0
        frames_done = 0
        frame_index = 0
        bright_sum = 0.0
        bright_count = 0
        evidence: List[Dict] = []
        tracker = _WorkerTracker()
        video_w = 0.0
        video_h = 0.0
        last_scale = 1.0

        fps = float(capture.get(cv2.CAP_PROP_FPS) or 30.0)
        total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

        # Spread the fixed sample budget evenly across the WHOLE clip so late
        # footage (e.g. workers arriving halfway through) is represented.
        if total_frames > 0:
            step = max(1, int(total_frames // MAX_SAMPLES))
        else:
            step = SAMPLE_INTERVAL

        def _consume(frame, frame_index, scale):
            nonlocal vehicle_max, workers_max, video_w, video_h, last_scale
            last_scale = float(scale) if scale else 1.0
            work = frame
            h, w = work.shape[:2]
            video_w = float(w / scale) if scale else float(w)
            video_h = float(h / scale) if scale else float(h)
            base_dets = base.detect_from_frame(work)
            persons = [d for d in base_dets if d.get("class_id") == 0]
            # Person anchors stay in the SAME (resized) coordinate space as
            # `work` so PPE boxes overlap them correctly for per-worker scoring.
            person_boxes = [
                {
                    "bbox": list(d["bbox"]),
                    "confidence": d.get("confidence", 0.9),
                }
                for d in persons
            ]

            ppe_result = ppe.analyze_workers(work, person_detections=person_boxes)

            # Associate this frame's workers into tracked identities, then stamp
            # the stable tracked id on the per-frame evidence for coherence.
            assigned = tracker.observe_many(ppe_result.get("workers", []), frame_index, fps)

            # Persist per-frame evidence for downstream agents / UI.
            evidence.append({
                "frame_number": frame_index,
                "timestamp": round(frame_index / max(fps, 1.0), 2),
                "detections": [
                    {
                        "label": d.get("label", "unknown"),
                        "class_name": d.get("label", "unknown"),
                        "class_id": d.get("class_id"),
                        "confidence": round(d.get("confidence", 0.0), 3),
                        "bbox": [round(v / scale, 1) for v in d["bbox"]],
                    }
                    for d in base_dets
                ],
                "workers": [
                    {
                        "worker_id": assigned.get(_box_key(w3.get("bbox") or []), w3.get("worker_id")),
                        "ppe_status": w3.get("ppe_status"),
                        "bbox": [round(v / scale, 1) for v in (w3.get("bbox") or [])],
                        "confidence": w3.get("confidence"),
                    }
                    for w3 in ppe_result.get("workers", [])
                ],
                "worker_count": len(ppe_result.get("workers", [])),
                "vehicle_count": sum(1 for d in base_dets if d.get("class_id") in (2, 5, 7, 8)),
                "violations": sum(
                    1 for w2 in ppe_result.get("workers", [])
                    if w2.get("ppe_status") == "non_compliant"
                ),
            })

            # The observe_many above already registered these workers.
            person_count = len(ppe_result.get("workers", []))
            vehicle_count = sum(1 for d in base_dets if d.get("class_id") in (2, 5, 7, 8))

            workers_max = max(workers_max, person_count)
            vehicle_max = max(vehicle_max, vehicle_count)

            nonlocal best_person_count, best_frame_dets, best_workers, best_ppe_meta
            if person_count > best_person_count:
                best_person_count = person_count
                best_frame_dets = [
                    {
                        "label": d.get("label", "unknown"),
                        "class_id": d.get("class_id"),
                        "confidence": round(d.get("confidence", 0.0), 3),
                        "bbox": [round(v / scale, 1) for v in d["bbox"]],
                    }
                    for d in base_dets
                ]
                best_workers = list(ppe_result.get("workers", []))
                best_ppe_meta = dict(ppe_result)
            return person_count, vehicle_count

        while frames_done < MAX_SAMPLES:
            if total_frames > 0:
                target = frames_done * step
                capture.set(cv2.CAP_PROP_POS_FRAMES, target)
                ok, frame = capture.read()
                if not ok or frame is None:
                    break
                frame_index = target + 1
            else:
                ok, frame = capture.read()
                if not ok or frame is None:
                    break
                if frame_index % SAMPLE_INTERVAL != 0:
                    frame_index += 1
                    continue
                frame_index += 1

            work = frame
            scale = 1.0
            h, w = frame.shape[:2]
            if w > PROCESS_WIDTH:
                scale = PROCESS_WIDTH / w
                work = cv2.resize(frame, (PROCESS_WIDTH, int(h * scale)))

            try:
                bright_sum += float(cv2.mean(cv2.cvtColor(work, cv2.COLOR_BGR2GRAY))[0])
                bright_count += 1
            except Exception:  # noqa: BLE001
                pass

            _consume(work, frame_index, scale)
            frames_done += 1

        # Top-level PPE metrics come from the SAME tracked worker assessments the
        # downstream agents consume, so report compliance and per-worker PPE
        # never contradict each other.
        tracked_workers = tracker.final_workers(fps, last_scale)
        top_workers = tracked_workers
        report["worker_count"] = len(tracked_workers)  # distinct tracked workers
        report["worker_peak"] = workers_max             # max concurrent in a frame
        report["vehicle_count"] = vehicle_max
        report["workers"] = tracked_workers
        report["helmet_violations"] = sum(
            1 for w in top_workers
            if w.get("ppe_status") == "non_compliant"
            and "helmet" in (w.get("missing_ppe") or [])
        )
        report["vest_violations"] = sum(
            1 for w in top_workers
            if w.get("ppe_status") == "non_compliant"
            and "vest" in (w.get("missing_ppe") or [])
        )
        report["other_violations"] = sum(
            1 for w in top_workers
            if w.get("ppe_status") == "non_compliant"
            and w.get("missing_ppe")
            and not any(x in (w.get("missing_ppe") or []) for x in ("helmet", "vest"))
        )
        report["total_violations"] = (
            report["helmet_violations"]
            + report["vest_violations"]
            + report["other_violations"]
        )
        compliant = sum(1 for w in top_workers if w.get("ppe_status") == "compliant")
        conclusive = sum(
            1 for w in top_workers
            if w.get("ppe_status") in ("compliant", "non_compliant")
        )
        if conclusive:
            report["ppe_compliance"] = round((compliant / conclusive) * 100, 1)
        report["detected_objects"] = best_frame_dets
        report["ppe_workers"] = {
            "workers": top_workers,
            "model_used": best_ppe_meta.get("model_used", "yolov8n.pt"),
            "compliant_count": compliant,
            "non_compliant_count": conclusive - compliant,
            "insufficient_evidence_count": len(top_workers) - conclusive,
            "conclusive_count": conclusive,
            "compliance_rate": round(compliant / conclusive, 3) if conclusive else 1.0,
            "total_workers": len(top_workers),
            "image_width": round(video_w),
            "image_height": round(video_h),
        }
        report["frames_analyzed"] = frames_done
        report["model_used"] = best_ppe_meta.get("model_used", "yolov8n.pt")
        report["lighting_condition"] = _lighting_from_brightness(bright_sum, bright_count)
        report["frame_evidence"] = evidence

        # Accident zones derived from ACTUAL spatial detections in the frames.
        try:
            from app.agents.safety_agent.accident_zone_analyzer import AccidentZoneAnalyzer

            report["accident_zones"] = AccidentZoneAnalyzer().analyze_from_video(
                evidence, video_w, video_h
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Accident-zone analysis skipped: %s", exc)
            report["accident_zones"] = {
                "available": False,
                "note": "Accident-zone analysis could not be completed.",
                "zones": [],
                "top_accident_zone": None,
                "overall_accident_risk": {"score": 0.0, "risk_level": "LOW", "evidence_available": False},
            }
    except Exception as exc:  # noqa: BLE001
        logger.exception("Video analysis failed for source %s", source)
        report["error"] = str(exc)
    finally:
        capture.release()

    return report


def attach_worker_counts(
    equipment_data: Optional[List[Dict[str, Any]]],
    worker_count: int,
) -> List[Dict[str, Any]]:
    """Bind the real video-detected worker count onto active equipment.

    Equipment telemetry (status/activity) stays as reported, but the
    ``nearby_worker_count`` driving equipment-proximity hazards is set from the
    real video detection so risk factors follow what the video actually shows.
    """
    workers = max(0, int(worker_count or 0))
    bound: List[Dict[str, Any]] = []
    for eq in list(equipment_data or []):
        item = dict(eq)
        status = str(item.get("status", "")).lower().strip()
        activity = str(item.get("activity", "")).lower().strip()
        if status in ("active", "operating", "running") or activity:
            item["nearby_worker_count"] = workers
        bound.append(item)
    return bound


def clear_cache() -> None:
    """Drop cached reports (e.g. when a new video is configured)."""
    with _report_lock:
        _report_cache.clear()


def _lighting_from_brightness(bright_sum: float, bright_count: int) -> str:
    """Derive a lighting-condition label from the mean frame brightness.

    The value is computed from the sampled video frames themselves, so it is a
    genuine observation from the footage, not an assumption. Brightness is the
    mean grey level over a 0-255 scale.
    """
    if not bright_count:
        return ""
    mean = bright_sum / bright_count
    if mean >= 110:
        return "Good"
    if mean >= 70:
        return "Adequate"
    if mean >= 40:
        return "Poor"
    return "Dark"