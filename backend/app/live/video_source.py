"""
Video source abstraction.

The pipeline consumes frames through a common ``VideoSource`` interface so the
source can later be a local file, webcam, RTSP stream, or CCTV/IP camera without
touching the risk engine or detection layer.

Supported source kinds (decided from the source value):
  * numeric device index  -> webcam (e.g. 0)
  * URL starting ws/wss/rtsp/http(s) -> network stream
  * otherwise              -> local video file path
"""

from __future__ import annotations

import os
from typing import Optional

import cv2


class VideoSource:
    """Reads frames from a file, webcam, or network stream via OpenCV."""

    def __init__(self, source: str | int, loop: bool = True) -> None:
        self.source = source
        self.loop = loop
        self._cap: Optional[cv2.VideoCapture] = None
        self._kind = self.kind(source)

    @staticmethod
    def kind(source) -> str:
        if isinstance(source, int):
            return "webcam"
        s = str(source).lower()
        if s.startswith(("ws://", "wss://", "rtsp://", "rtmp://", "http://", "https://")):
            return "stream"
        return "file"

    def open(self) -> None:
        """Open the capture device. Raises RuntimeError if unavailable."""
        self.close()
        if isinstance(self.source, int):
            cap = cv2.VideoCapture(self.source)
        else:
            path = str(self.source)
            if not os.path.exists(path):
                raise RuntimeError(f"Video source file not found: {path}")
            cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            raise RuntimeError(
                f"Cannot open video source: {self.source}"
            )
        self._cap = cap

    def read(self):
        """Read the next frame. Returns (ok, frame) like cv2.VideoCapture.

        Local file sources loop back to the beginning by default so the live
        pipeline behaves like a continuous camera feed.
        """
        if self._cap is None:
            raise RuntimeError("Video source not opened")
        ok, frame = self._cap.read()
        if not ok and self._kind == "file" and self.loop:
            self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = self._cap.read()
        return ok, frame

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    @property
    def is_opened(self) -> bool:
        return self._cap is not None and self._cap.isOpened()
