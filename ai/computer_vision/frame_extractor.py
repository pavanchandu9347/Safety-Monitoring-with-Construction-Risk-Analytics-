"""
Video frame extraction utilities for the Construction Risk Intelligence Platform.
Extracts frames from video files at configurable intervals.
"""

import logging
from dataclasses import dataclass
from typing import Generator, List, Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class VideoMetadata:
    """Metadata about a video file."""
    path: str
    fps: float
    frame_count: int
    width: int
    height: int
    duration_seconds: float


class FrameExtractor:
    """Extract frames from video files for construction site analysis.

    Supports extraction at fixed intervals (every Nth frame) or at specific
    timestamps. Frames are returned as numpy arrays in BGR format (OpenCV default).
    """

    def __init__(self, frame_interval: int = 30):
        """Initialize the frame extractor.

        Args:
            frame_interval: Extract every Nth frame. Default 30 (~1 fps for 30fps video).
        """
        if frame_interval < 1:
            raise ValueError("frame_interval must be >= 1")
        self.frame_interval = frame_interval

    def get_video_metadata(self, video_path: str) -> Optional[VideoMetadata]:
        """Retrieve metadata about a video file without reading frames.

        Args:
            video_path: Path to the video file.

        Returns:
            VideoMetadata or None if the file cannot be opened.
        """
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.error("Cannot open video file: %s", video_path)
            return None

        try:
            fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            duration = frame_count / fps if fps > 0 else 0.0

            return VideoMetadata(
                path=video_path,
                fps=fps,
                frame_count=frame_count,
                width=width,
                height=height,
                duration_seconds=duration,
            )
        finally:
            cap.release()

    def extract_frames(
        self,
        video_path: str,
        frame_interval: Optional[int] = None,
        max_frames: Optional[int] = None,
    ) -> List[np.ndarray]:
        """Extract frames from a video at the specified interval.

        Args:
            video_path: Path to the video file.
            frame_interval: Override the instance frame_interval for this extraction.
            max_frames: Maximum number of frames to extract (None for all).

        Returns:
            List of frames as numpy arrays (BGR format).
        """
        interval = frame_interval if frame_interval is not None else self.frame_interval
        frames = list(self._iter_frames(video_path, interval, max_frames))
        logger.info(
            "Extracted %d frames from %s (interval=%d)",
            len(frames), video_path, interval,
        )
        return frames

    def iter_frames(
        self,
        video_path: str,
        frame_interval: Optional[int] = None,
        max_frames: Optional[int] = None,
    ) -> Generator[np.ndarray, None, None]:
        """Generator that yields frames one at a time for memory-efficient processing.

        Args:
            video_path: Path to the video file.
            frame_interval: Override the instance frame_interval.
            max_frames: Maximum number of frames to yield.

        Yields:
            Frames as numpy arrays (BGR format).
        """
        yield from self._iter_frames(video_path, frame_interval, max_frames)

    def extract_frame_at(
        self,
        video_path: str,
        frame_number: int,
    ) -> Optional[np.ndarray]:
        """Extract a single specific frame by frame number.

        Args:
            video_path: Path to the video file.
            frame_number: Zero-indexed frame number to extract.

        Returns:
            The frame as a numpy array, or None if extraction fails.
        """
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.error("Cannot open video file: %s", video_path)
            return None

        try:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            ret, frame = cap.read()
            if not ret or frame is None:
                logger.warning("Failed to read frame %d from %s", frame_number, video_path)
                return None
            return frame
        finally:
            cap.release()

    def _iter_frames(
        self,
        video_path: str,
        frame_interval: Optional[int],
        max_frames: Optional[int],
    ) -> Generator[np.ndarray, None, None]:
        """Internal generator for frame extraction."""
        interval = frame_interval if frame_interval is not None else self.frame_interval

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.error("Cannot open video file: %s", video_path)
            return

        try:
            frame_idx = 0
            extracted = 0

            while True:
                ret, frame = cap.read()
                if not ret or frame is None:
                    break

                if frame_idx % interval == 0:
                    yield frame
                    extracted += 1

                    if max_frames is not None and extracted >= max_frames:
                        return

                frame_idx += 1
        finally:
            cap.release()
