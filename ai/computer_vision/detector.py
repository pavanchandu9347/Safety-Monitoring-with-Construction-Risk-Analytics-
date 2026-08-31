"""
Construction site object detection using YOLO (ultralytics).

Detects construction-relevant objects such as workers (persons), excavators,
dump trucks, and other construction vehicles in images and video frames.
"""

import logging
import os
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# COCO class mapping for construction-relevant objects.
# Includes classes commonly found on construction sites.
CONSTRUCTION_CLASSES = frozenset({
    0,    # person
    1,    # bicycle
    2,    # car
    3,    # motorcycle
    5,    # bus
    7,    # truck
    8,    # boat (often used for transport on water)
    14,   # bench (common site fixture)
})

COCO_LABELS: Dict[int, str] = {
    0: "person",
    1: "bicycle",
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
    8: "boat",
    14: "bench",
}

DEFAULT_CONF_THRESHOLD: float = 0.35
DEFAULT_IOU_THRESHOLD: float = 0.45
MODEL_NAME: str = "yolov8n.pt"
CONFIDENCE_SEED: int = 42


class ConstructionSiteDetector:
    """Object detection pipeline for construction site imagery.

    Uses a YOLOv8 model from ultralytics to detect workers, excavators,
    and heavy construction vehicles. Results are returned as structured
    dictionaries for downstream risk analysis.

    Attributes:
        model_path: Path or name of the YOLO model checkpoint.
        conf: Confidence threshold for detections.
        iou: IoU threshold for NMS.
        classes: Set of COCO class IDs to keep (None keeps all).
        _model: Loaded YOLO model or None if unavailable.
    """

    def __init__(
        self,
        model_path: str = MODEL_NAME,
        conf: float = DEFAULT_CONF_THRESHOLD,
        iou: float = DEFAULT_IOU_THRESHOLD,
        classes: Optional[List[int]] = None,
        device: str = "cpu",
    ):
        """Initialize the detector.

        Args:
            model_path: Model checkpoint path/name. yolov8n.pt auto-downloads.
            conf: Confidence threshold (0-1).
            iou: IoU NMS threshold (0-1).
            classes: Restrict detection to these COCO class IDs.
            device: Inference device ('cpu', 'cuda', 'mps', etc.).
        """
        self.model_path = model_path
        self.conf = conf
        self.iou = iou
        self.classes = list(classes) if classes else None
        self.device = device
        self._model = None
        self._deterministic_ready = False

    @property
    def model(self):
        """Lazily load and return the YOLO model."""
        if self._model is None:
            self._model = self._load_model()
        return self._model

    @property
    def available(self) -> bool:
        """Whether the underlying detection model is available."""
        try:
            return self.model is not None
        except Exception:
            return False

    def _load_model(self):
        """Load the YOLO model, handling import and download errors gracefully.

        Returns:
            Loaded model or None if unavailable.
        """
        try:
            from ultralytics import YOLO

            resolved_path = self.model_path
            if not os.path.isabs(resolved_path):
                resolved_path = self._resolve_model_path(resolved_path)

            model = YOLO(resolved_path)
            logger.info("Loaded YOLO model from %s", resolved_path)
            return model
        except ImportError:
            logger.error(
                "ultralytics is not installed. Run: pip install ultralytics"
            )
            return None
        except Exception as exc:
            logger.error(
                "Failed to load YOLO model %s: %s", self.model_path, exc
            )
            return None

    @staticmethod
    def _resolve_model_path(model_path: str) -> str:
        """Resolve a model name to a local file if it exists, else keep the name
        so ultralytics can auto-download it."""
        candidates = [
            model_path,
            os.path.join(os.getcwd(), model_path),
        ]
        for path in candidates:
            if os.path.exists(path):
                return path
        # ultralytics will download named models (e.g. yolov8n.pt)
        return model_path

    def _prepare_deterministic(self) -> None:
        """Configure determinism for reproducible detection results."""
        if self._deterministic_ready:
            return

        try:
            import random

            import numpy as np

            random.seed(CONFIDENCE_SEED)
            np.random.seed(CONFIDENCE_SEED)

            try:
                import torch

                torch.manual_seed(CONFIDENCE_SEED)
            except ImportError:
                pass
        except Exception as exc:
            logger.warning("Could not fully configure determinism: %s", exc)

        self._deterministic_ready = True

    def detect(self, image_path: str) -> List[Dict]:
        """Run detection on an image file on disk.

        Args:
            image_path: Path to the image file.

        Returns:
            List of detection dicts:
                {label, confidence, bbox (x1,y1,x2,y2), class_id}
            Empty list on error or no detections.
        """
        if not image_path or not os.path.exists(image_path):
            logger.warning("Image file not found: %s", image_path)
            return []

        model = self.model
        if model is None:
            logger.error("YOLO model unavailable; cannot run detection")
            return []

        self._prepare_deterministic()

        try:
            import cv2

            image = cv2.imread(image_path, cv2.IMREAD_COLOR)
            if image is None:
                logger.warning("Failed to read image (corrupt or unsupported): %s", image_path)
                return []

            return self.detect_from_frame(image)
        except Exception as exc:
            logger.error("Detection failed for %s: %s", image_path, exc)
            return []

    def detect_from_frame(self, frame) -> List[Dict]:
        """Run detection on an in-memory frame (numpy array or PIL image).

        Args:
            frame: Image as numpy array (BGR for OpenCV) or PIL image.

        Returns:
            List of detection dicts.
            Empty list on error or no detections.
        """
        if frame is None:
            logger.warning("Received empty frame for detection")
            return []

        model = self.model
        if model is None:
            logger.error("YOLO model unavailable; cannot run detection")
            return []

        self._prepare_deterministic()

        try:
            results = model.predict(
                source=frame,
                conf=self.conf,
                iou=self.iou,
                classes=self.classes,
                device=self.device,
                verbose=False,
            )

            return self._format_results(results)
        except Exception as exc:
            logger.error("Detection failed on frame: %s", exc)
            return []

    def detect_from_video(
        self,
        video_path: str,
        frame_interval: int = 30,
        max_frames: Optional[int] = None,
    ) -> List[Dict]:
        """Run detection across a video, sampling frames at an interval.

        Args:
            video_path: Path to the video file.
            frame_interval: Process every Nth frame.
            max_frames: Maximum number of frames to process (None for all).

        Returns:
            List of per-frame result dicts:
                {
                    frame_index: int,
                    detections: List[dict],
                }
            Empty list on error.
        """
        from .frame_extractor import FrameExtractor

        if not video_path or not os.path.exists(video_path):
            logger.warning("Video file not found: %s", video_path)
            return []

        extractor = FrameExtractor(frame_interval=frame_interval)

        per_frame_results: List[Dict] = []
        for frame_idx, frame in enumerate(
            extractor.iter_frames(video_path, frame_interval, max_frames)
        ):
            detections = self.detect_from_frame(frame)
            per_frame_results.append(
                {
                    "frame_index": frame_idx * frame_interval,
                    "detections": detections,
                }
            )

        logger.info(
            "Processed %d frames from %s", len(per_frame_results), video_path
        )
        return per_frame_results

    def _format_results(self, results) -> List[Dict]:
        """Convert ultralytics results into structured detection dicts."""
        detections: List[Dict] = []

        if not results:
            return detections

        for result in results:
            try:
                boxes = result.boxes
                if boxes is None or len(boxes) == 0:
                    continue

                for box in boxes:
                    class_id = int(box.cls.item())
                    confidence = float(box.conf.item())

                    x1, y1, x2, y2 = [float(v) for v in box.xyxy[0].tolist()]
                    label = map_class_label(class_id)

                    detections.append(
                        {
                            "label": label,
                            "confidence": confidence,
                            "bbox": (x1, y1, x2, y2),
                            "class_id": class_id,
                        }
                    )
            except Exception as exc:
                logger.warning("Error formatting detection result: %s", exc)
                continue

        # Sort deterministically by confidence (desc) then label for stable output.
        detections.sort(
            key=lambda d: (d["confidence"], d["label"]),
            reverse=True,
        )
        return detections

    def count_workers(self, detections: List[Dict]) -> int:
        """Count worker detections (persons) in a detection list."""
        return sum(1 for d in detections if d["class_id"] == 0)

    def count_vehicles(self, detections: List[Dict]) -> int:
        """Count construction vehicle detections in a detection list."""
        vehicle_classes = {2, 5, 7, 8}
        return sum(1 for d in detections if d["class_id"] in vehicle_classes)


def map_class_label(class_id: int) -> str:
    """Map a COCO class id to a human-readable label.

    Returns the COCO name for known ids and a fallback for unknown ids.

    Args:
        class_id: COCO class integer id.

    Returns:
        String label.
    """
    if class_id in COCO_LABELS:
        return COCO_LABELS[class_id]
    return "unknown_class_{}".format(class_id)
