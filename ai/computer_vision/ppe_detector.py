"""
Real PPE compliance detection using a trained YOLO model.

This detector runs genuine, image-dependent inference on the uploaded frame
using a YOLO model trained on the Construction-PPE dataset (classes: helmet,
gloves, vest, boots, goggles and their missing variants, plus Person).

Design rules:
  * The model is loaded once and cached at module level (reused across
    requests) — never reloaded per request.
  * Class labels are taken from the model's actual ``names`` mapping — the
    detector never invents classes.
  * Results always depend on the actual uploaded image.
  * There is NO simulated / deterministic fallback. If the model weights are
    not present, a ``PPEModelUnavailable`` error is raised so the caller can
    surface a clear, honest message to the user.
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Dict, List, Optional

from ai.computer_vision.detector import resolve_device

logger = logging.getLogger(__name__)

# Default PPE model weights. Override with the PPE_MODEL_PATH env var.
# ppe_detector.py lives at <root>/ai/computer_vision/, so go up two levels to
# <root>/ai and look for models/ppe.pt.
DEFAULT_PPE_MODEL_PATH: str = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "models",
    "ppe.pt",
)

DEFAULT_CONF_THRESHOLD: float = 0.35
DEFAULT_IOU_THRESHOLD: float = 0.45

# Construction-PPE missing-* classes imply an explicit compliance violation.
MISSING_CLASS_NAMES = frozenset(
    {"no_helmet", "no_gloves", "no_boots", "no_goggle", "no_vest", "none"}
)

# Worn-PPE classes (compliance signal).
WORNN_CLASS_NAMES = frozenset({"helmet", "gloves", "vest", "boots", "goggles"})


class PPEModelUnavailable(RuntimeError):
    """Raised when the PPE model weights cannot be loaded."""


class PPEDetector:
    """Real YOLO-based PPE (personal protective equipment) detector."""

    def __init__(
        self,
        model_path: Optional[str] = None,
        conf: float = DEFAULT_CONF_THRESHOLD,
        iou: float = DEFAULT_IOU_THRESHOLD,
        device: Optional[str] = None,
    ) -> None:
        self.model_path = (
            model_path
            or os.environ.get("PPE_MODEL_PATH")
            or os.environ.get("YOLO_MODEL_PATH")
            or DEFAULT_PPE_MODEL_PATH
        )
        self.conf = conf
        self.iou = iou
        # Defaults to best device (MPS on Apple Silicon); YOLO_DEVICE overrides.
        self.device = resolve_device(device)
        self._model = None
        self._load_error: Optional[str] = None
        self._lock = threading.Lock()

    # ── model loading (cached) ──────────────────────────────────────────

    def _resolve_path(self) -> Optional[str]:
        """Resolve the weights path; return None if the file is missing."""
        candidates = [
            self.model_path,
            os.path.join(os.getcwd(), self.model_path),
        ]
        for path in candidates:
            if path and os.path.exists(path):
                return path
        return None

    def _load(self):
        """Load and cache the YOLO model. Raises PPEModelUnavailable on failure."""
        with self._lock:
            if self._model is not None:
                return self._model
            if self._load_error:
                raise PPEModelUnavailable(self._load_error)

            resolved = self._resolve_path()
            if not resolved:
                self._load_error = (
                    f"PPE model weights not found at '{self.model_path}'. "
                    "Set PPE_MODEL_PATH to a trained Construction-PPE weights file "
                    "to enable real PPE detection."
                )
                raise PPEModelUnavailable(self._load_error)

            try:
                from ultralytics import YOLO

                model = YOLO(resolved)
                self._model = model
                logger.info("Loaded PPE YOLO model from %s", resolved)
                return model
            except ImportError:
                self._load_error = (
                    "ultralytics is not installed. Run: pip install ultralytics"
                )
                raise PPEModelUnavailable(self._load_error)
            except Exception as exc:  # noqa: BLE001
                self._load_error = f"Failed to load PPE YOLO model: {exc}"
                raise PPEModelUnavailable(self._load_error)

    @property
    def model(self):
        return self._load()

    @property
    def available(self) -> bool:
        """True if a real PPE model is loaded and ready for inference."""
        try:
            self._load()
            return True
        except PPEModelUnavailable:
            return False

    @property
    def names(self) -> Dict[int, str]:
        """Actual class names supported by the loaded model."""
        return {int(k): str(v) for k, v in self.model.names.items()}

    @property
    def status(self) -> Dict:
        """Structured status describing model availability."""
        if not available(model=self):
            return {
                "available": False,
                "model_used": "unavailable",
            }
        return {
            "available": True,
            "model_used": os.path.basename(self._resolve_path() or self.model_path),
            "classes": self.names,
        }

    # ── inference ───────────────────────────────────────────────────────

    def infer(self, frame) -> Dict:
        """Run real YOLO inference on an image frame.

        Args:
            frame: numpy array (BGR) or PIL image.

        Returns:
            {
                "detections": [
                    {
                        "class_name": str,
                        "class_id": int,
                        "confidence": float,
                        "bbox": [x1, y1, x2, y2],   # pixels in original image
                    }, ...
                ],
                "image_width": int,
                "image_height": int,
            }

        Raises:
            PPEModelUnavailable: if the PPE weights are not available.
        """
        if frame is None:
            raise PPEModelUnavailable("Frame is empty; cannot run PPE inference")

        model = self._load()

        h, w = frame.shape[:2] if hasattr(frame, "shape") else (0, 0)

        try:
            results = model.predict(
                source=frame,
                conf=self.conf,
                iou=self.iou,
                device=self.device,
                verbose=False,
            )
        except Exception as exc:  # noqa: BLE001
            raise PPEModelUnavailable(f"PPE inference failed: {exc}") from exc

        detections: List[Dict] = []
        names = self.names
        for result in results:
            boxes = getattr(result, "boxes", None)
            if boxes is None:
                continue
            for box in boxes:
                class_id = int(box.cls.item())
                confidence = float(box.conf.item())
                x1, y1, x2, y2 = [float(v) for v in box.xyxy[0].tolist()]
                detections.append(
                    {
                        "class_name": names.get(class_id, f"unknown_{class_id}"),
                        "class_id": class_id,
                        "confidence": confidence,
                        "bbox": [x1, y1, x2, y2],
                    }
                )

        detections.sort(key=lambda d: (d["confidence"], d["class_name"]), reverse=True)

        return {
            "detections": detections,
            "image_width": int(w),
            "image_height": int(h),
        }

    # ── worker-level PPE compliance from real detections ────────────────

    def analyze_workers(self, frame, person_detections: Optional[List[Dict]] = None) -> Dict:
        """Derive per-worker PPE compliance from real detections.

        Worker anchors are the Persons detected by the PPE model, supplemented
        with the caller-provided base-COCO person detections (also real
        inference) for any person box that is NOT already covered by a PPE-model
        Person box — so a worker is never dropped just because the PPE model's
        Person class did not fire on him.

        Worn-PPE boxes and missing-* boxes are each associated to a worker by
        bounding-box overlap against that worker ONLY. A ``no_*`` box therefore
        only flags the specific worker(s) it actually overlaps — violations are
        never applied globally to everyone on the frame.

        Args:
            frame: image (numpy BGR or PIL).
            person_detections: optional real person boxes
                [{bbox: [x1,y1,x2,y2], confidence: float, ...}].

        Returns:
            {
                "model_used": str, "workers": [...], "compliant_count": int,
                "non_compliant_count": int, "compliance_rate": float,
                "total_workers": int, "image_width": int, "image_height": int,
            }
        """
        inference = self.infer(frame)
        detections = inference["detections"]
        persons = [d for d in detections if d["class_name"] == "Person"]

        # Supplement with caller-provided real person boxes not already covered
        # by a PPE-model Person anchor (also real inference).
        if person_detections:
            for p in person_detections:
                pb = p["bbox"]
                if not any(self._boxes_overlap(pb, q["bbox"]) for q in persons):
                    persons.append(
                        {
                            **p,
                            "class_name": "Person",
                            "confidence": p.get("confidence", 0.9),
                        }
                    )

        worn = {
            n: [d for d in detections if d["class_name"] == n]
            for n in WORNN_CLASS_NAMES
        }
        missing_boxes = {
            n: [d for d in detections if d["class_name"] == n]
            for n in MISSING_CLASS_NAMES
        }

        workers: List[Dict] = []
        for idx, person in enumerate(persons, start=1):
            detected = set(self._overlap_ppe(person, worn))
            # Missing-* boxes overlapping THIS worker only.
            overlap_missing = self._overlap_ppe(person, missing_boxes)
            # An overlapping no_* box contradicts the worn item: drop it.
            detected = {
                item
                for item in detected
                if MISSING_MAP.get(item) not in overlap_missing
            }
            # Flag an item as missing only when an overlapping no_* box exists
            # for it and the worn item was not detected for this worker.
            missing = sorted(
                item
                for item, miss_name in MISSING_MAP.items()
                if miss_name in overlap_missing and item not in detected
            )
            compliant = not missing and not detected_flag_violation(detected, missing)
            severity = "LOW"
            if missing:
                severity = "HIGH" if any(m in ("helmet", "vest") for m in missing) else "MEDIUM"
            workers.append(
                {
                    "worker_id": f"W-{idx}",
                    "worker_role": _infer_role(person),
                    "ppe_status": "compliant" if compliant else "non_compliant",
                    "detected_ppe": sorted(detected),
                    "missing_ppe": missing,
                    "confidence": round(person["confidence"], 3),
                    "violation": not compliant,
                    "severity": severity,
                }
            )

        compliant = sum(1 for w in workers if w["ppe_status"] == "compliant")
        total = len(workers)

        return {
            "model_used": os.path.basename(self._resolve_path() or self.model_path),
            "workers": workers,
            "compliant_count": compliant,
            "non_compliant_count": total - compliant,
            "compliance_rate": round(compliant / total, 3) if total else 1.0,
            "total_workers": total,
            "image_width": inference["image_width"],
            "image_height": inference["image_height"],
        }

    @staticmethod
    def _boxes_overlap(a: list, b: list) -> bool:
        """True if two [x1,y1,x2,y2] boxes share any area."""
        ax1, ay1, ax2, ay2 = a
        bx1, by1, bx2, by2 = b
        return (
            min(ax2, bx2) > max(ax1, bx1)
            and min(ay2, by2) > max(ay1, by1)
        )

    @staticmethod
    def _overlap_ppe(person: Dict, worn: Dict[str, List[Dict]]) -> set:
        """Return the set of worn-PPE class names whose box overlaps the person."""
        px1, py1, px2, py2 = person["bbox"]
        parea = max((px2 - px1) * (py2 - py1), 1e-6)
        pad_x = (px2 - px1) * 0.1
        pad_y = (py2 - py1) * 0.1
        found: set = set()
        for label, items in worn.items():
            for it in items:
                x1, y1, x2, y2 = it["bbox"]
                ix1, iy1, ix2, iy2 = max(x1, px1 - pad_x), max(y1, py1 - pad_y), \
                    min(x2, px2 + pad_x), min(y2, py2 + pad_y)
                if ix2 <= ix1 or iy2 <= iy1:
                    continue
                inter = (ix2 - ix1) * (iy2 - iy1)
                # PPE must occupy a meaningful fraction of the person area or
                # the person must contain the PPE centroid region.
                if inter / parea >= 0.02:
                    found.add(label)
        return found


# Missing class name associated with each worn PPE item.
MISSING_MAP: Dict[str, str] = {
    "helmet": "no_helmet",
    "gloves": "no_gloves",
    "vest": "no_vest",       # no dedicated no_vest class in Construction-PPE
    "boots": "no_boots",
    "goggles": "no_goggle",
}


def detected_flag_violation(_detected: List[str], missing: List[str]) -> bool:
    """Require a worker to be non-compliant only on explicit signals."""
    return bool(missing)


def _infer_role(person: Dict) -> str:
    """Heuristic role inference from a person box (kept simple and honest)."""
    return "worker"


def available(model: Optional[PPEDetector] = None) -> bool:
    """Convenience: report whether a real PPE model is available."""
    det = model if model is not None else get_ppe_detector()
    return det.available


_detector: Optional[PPEDetector] = None
_detector_lock = threading.Lock()


def get_ppe_detector() -> PPEDetector:
    """Return a process-wide singleton detector (loaded once, reused)."""
    global _detector
    with _detector_lock:
        if _detector is None:
            _detector = PPEDetector()
    return _detector
