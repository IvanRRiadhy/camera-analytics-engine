"""
Decoupled Video Ingestion Backend Strategy (IVideoBackend).

Abstracts frame decoding from core ingestion pipeline:
- OpenCVBackend: Default cv2.VideoCapture decoder.
- GStreamerBackend: Hardware-accelerated GStreamer NVMM pipeline for NVIDIA Jetson devices.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Optional, Tuple
import numpy as np

logger = logging.getLogger(__name__)


class IVideoBackend(ABC):
    """Abstract strategy interface for video frame ingestion backends."""

    @abstractmethod
    def open(self, source_uri: str) -> bool:
        """Open video stream or RTSP source.

        Args:
            source_uri: RTSP URL, video file path, or USB camera index string.
        """
        pass

    @abstractmethod
    def read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        """Retrieve next decoded BGR frame matrix.

        Returns:
            Tuple[bool, Optional[np.ndarray]]: (Success flag, Frame image matrix)
        """
        pass

    @abstractmethod
    def release(self) -> None:
        """Close video stream and free hardware decoders."""
        pass


class OpenCVBackend(IVideoBackend):
    """Standard OpenCV cv2.VideoCapture decoder backend."""

    def __init__(self) -> None:
        self._cap: Optional[Any] = None
        self._uri: str = ""

    def open(self, source_uri: str) -> bool:
        """Open video stream using OpenCV."""
        import cv2

        self._uri = source_uri
        # Handle string integer for USB cameras
        if source_uri.isdigit():
            self._cap = cv2.VideoCapture(int(source_uri))
        else:
            self._cap = cv2.VideoCapture(source_uri)

        is_open = self._cap is not None and self._cap.isOpened()
        if is_open:
            logger.info("OpenCVBackend opened source successfully: %s", source_uri)
        else:
            logger.error("OpenCVBackend failed to open source: %s", source_uri)
        return is_open

    def read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        """Read next frame via OpenCV."""
        if self._cap is None or not self._cap.isOpened():
            return False, None
        ret, frame = self._cap.read()
        return ret, frame

    def release(self) -> None:
        """Release OpenCV video capture."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None
            logger.info("OpenCVBackend released source: %s", self._uri)


class GStreamerBackend(IVideoBackend):
    """Hardware-accelerated GStreamer NVMM decoder backend for NVIDIA Jetson."""

    def __init__(self) -> None:
        self._cap: Optional[Any] = None
        self._uri: str = ""

    def _build_pipeline(self, rtsp_url: str) -> str:
        """Construct GStreamer NVMM hardware acceleration pipeline string."""
        return (
            f"rtspsrc location={rtsp_url} latency=100 ! "
            "rtph264depay ! h264parse ! nvv4l2decoder ! "
            "nvvideoconvert ! video/x-raw, format=BGRx ! "
            "videoconvert ! video/x-raw, format=BGR ! appsink drop=1"
        )

    def open(self, source_uri: str) -> bool:
        """Open video stream using GStreamer NVMM pipeline."""
        import cv2

        self._uri = source_uri
        pipeline = self._build_pipeline(source_uri)
        self._cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)

        is_open = self._cap is not None and self._cap.isOpened()
        if is_open:
            logger.info("GStreamerBackend opened NVMM pipeline successfully for: %s", source_uri)
        else:
            logger.warning("GStreamerBackend failed. Falling back to OpenCVBackend for: %s", source_uri)
            fallback = OpenCVBackend()
            res = fallback.open(source_uri)
            self._cap = fallback._cap
            return res
        return is_open

    def read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        """Read next frame via GStreamer."""
        if self._cap is None or not self._cap.isOpened():
            return False, None
        ret, frame = self._cap.read()
        return ret, frame

    def release(self) -> None:
        """Release GStreamer capture."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None
            logger.info("GStreamerBackend released source: %s", self._uri)
