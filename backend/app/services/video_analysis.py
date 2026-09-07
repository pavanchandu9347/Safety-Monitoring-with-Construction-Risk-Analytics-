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

logger = logging.getLogger(__name__)

# The default video source is the SAME one the live pipeline uses (env-driven,
# falling back to the project's construction site demo clip).
DEFAULT_VIDEO_SOURCE: str = os.environ.get(
    "VIDEO_SOURCE",
    "/Users/pavanchandu/Downloads/Site_construction.mp4",
)

DEFAULT_CONF: float = float(os.environ.get("YOLO_CONFIDENCE", "0.45"))

# Number of video frames to skip between analysis samples.
SAMPLE_INTERVAL: int = 25
# Maximum number of sampled frames analyzed per report.
MAX_SAMPLES: int = 16
# Downscale width before inference (matches the live pipeline).
PROCESS_WIDTH: int = 1280
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
      3. the ``VIDEO_SOURCE`` env var (falling back to the demo clip).
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

    env = DEFAULT_VIDEO_SOURCE
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

    key = (str(source), round(confidence, 3))
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

        aggregated = {
            "helmet": 0,
            "vest": 0,
            "other": 0,
        }
        vehicle_max = 0
        workers_max = 0
        frames_done = 0
        frame_index = 0

        while frames_done < MAX_SAMPLES:
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

            # Recompute violations from per-worker real PPE attribution.
            helmet_v = sum(
                1 for w in ppe_result.get("workers", [])
                if "helmet" in (w.get("missing_ppe") or [])
            )
            vest_v = sum(
                1 for w in ppe_result.get("workers", [])
                if "vest" in (w.get("missing_ppe") or [])
            )
            other_v = sum(
                1 for w in ppe_result.get("workers", [])
                if w.get("missing_ppe")
                and not any(x in (w.get("missing_ppe") or []) for x in ("helmet", "vest"))
            )
            person_count = len(ppe_result.get("workers", []))
            vehicle_count = sum(1 for d in base_dets if d.get("class_id") in (2, 5, 7, 8))

            aggregated["helmet"] += helmet_v
            aggregated["vest"] += vest_v
            aggregated["other"] += other_v
            workers_max = max(workers_max, person_count)
            vehicle_max = max(vehicle_max, vehicle_count)

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

            frames_done += 1

        total_frames = max(frames_done, 1)
        report["worker_count"] = workers_max
        report["vehicle_count"] = vehicle_max
        report["helmet_violations"] = round(aggregated["helmet"] / total_frames)
        report["vest_violations"] = round(aggregated["vest"] / total_frames)
        report["other_violations"] = round(aggregated["other"] / total_frames)
        report["total_violations"] = (
            report["helmet_violations"]
            + report["vest_violations"]
            + report["other_violations"]
        )
        if workers_max:
            report["ppe_compliance"] = round(
                (1.0 - report["total_violations"] / workers_max) * 100, 1
            )
        report["detected_objects"] = best_frame_dets
        report["ppe_workers"] = best_ppe_meta or report["ppe_workers"]
        report["frames_analyzed"] = frames_done
        report["model_used"] = best_ppe_meta.get("model_used", "yolov8n.pt")
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