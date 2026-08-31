"""
Image preprocessing utilities for the Construction Risk Intelligence Platform.
Provides resize, normalize, and format conversion operations.
"""

from typing import Optional, Tuple

import cv2
import numpy as np


def resize_image(
    image: np.ndarray,
    target_size: Optional[Tuple[int, int]] = None,
    max_dim: Optional[int] = 640,
    maintain_aspect: bool = True,
) -> np.ndarray:
    """Resize image to target dimensions or max dimension while maintaining aspect ratio.

    Args:
        image: Input image as numpy array (H, W, C).
        target_size: Explicit (width, height) to resize to. Overrides max_dim.
        max_dim: Maximum dimension (width or height) if target_size is None.
        maintain_aspect: Whether to maintain aspect ratio when resizing.

    Returns:
        Resized image as numpy array.
    """
    if image is None or image.size == 0:
        raise ValueError("Input image is empty or None")

    h, w = image.shape[:2]

    if target_size is not None:
        return cv2.resize(image, target_size, interpolation=cv2.INTER_LINEAR)

    if max_dim is None:
        return image.copy()

    if maintain_aspect:
        scale = max_dim / max(h, w)
        if scale >= 1.0:
            return image.copy()
        new_w = int(w * scale)
        new_h = int(h * scale)
        return cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    else:
        return cv2.resize(image, (max_dim, max_dim), interpolation=cv2.INTER_LINEAR)


def normalize_image(
    image: np.ndarray,
    target_dtype: np.dtype = np.float32,
    scale: float = 255.0,
) -> np.ndarray:
    """Normalize image pixel values to [0, 1] range and cast to target dtype.

    Args:
        image: Input image as numpy array.
        target_dtype: Output data type (default float32).
        scale: Divisor for normalization (default 255.0 for uint8 images).

    Returns:
        Normalized image array.
    """
    if image is None or image.size == 0:
        raise ValueError("Input image is empty or None")

    normalized = image.astype(np.float32) / scale
    return normalized.astype(target_dtype)


def preprocess_for_detection(
    image: np.ndarray,
    input_size: Tuple[int, int] = (640, 640),
) -> np.ndarray:
    """Full preprocessing pipeline for YOLO detection.

    Resizes, normalizes, and converts BGR->RGB for model input.

    Args:
        image: Input BGR image.
        input_size: Target (width, height) for the model.

    Returns:
        Preprocessed image ready for model inference.
    """
    if image is None or image.size == 0:
        raise ValueError("Input image is empty or None")

    resized = cv2.resize(image, input_size, interpolation=cv2.INTER_LINEAR)
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
    normalized = rgb.astype(np.float32) / 255.0
    return normalized


def decode_image_bytes(image_bytes: bytes) -> Optional[np.ndarray]:
    """Decode image bytes into an OpenCV numpy array.

    Args:
        image_bytes: Raw image file bytes.

    Returns:
        Decoded BGR image or None if decoding fails.
    """
    if not image_bytes:
        return None

    nparr = np.frombuffer(image_bytes, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    return image


def crop_region(
    image: np.ndarray,
    bbox: Tuple[int, int, int, int],
    padding: int = 0,
) -> Optional[np.ndarray]:
    """Crop a region from an image given a bounding box.

    Args:
        image: Source image.
        bbox: (x1, y1, x2, y2) bounding box coordinates.
        padding: Optional padding around the crop region.

    Returns:
        Cropped image region or None if invalid.
    """
    if image is None:
        return None

    h, w = image.shape[:2]
    x1, y1, x2, y2 = bbox

    x1 = max(0, x1 - padding)
    y1 = max(0, y1 - padding)
    x2 = min(w, x2 + padding)
    y2 = min(h, y2 + padding)

    if x2 <= x1 or y2 <= y1:
        return None

    return image[y1:y2, x1:x2].copy()
