"""
RTSP Video Source implementation.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

import cv2

from camera_analytics.ingestion.sources.base import StreamPacket, VideoSource

logger = logging.getLogger(__name__)


class RTSPSource(VideoSource):
    """VideoSource implementation for network RTSP streams."""

    def __init__(self, uri: str, params: Optional[dict[str, Any]] = None) -> None:
        super().__init__(uri=uri, params=params)
        self._cap: Optional[cv2.VideoCapture] = None
        self._packet_count = 0

    def open(self) -> bool:
        if self._is_open and self._cap is not None:
            return True

        try:
            self._cap = cv2.VideoCapture(self._uri, cv2.CAP_FFMPEG)
            if self._cap.isOpened():
                self._is_open = True
                logger.info("RTSPSource: Successfully connected to RTSP stream '%s'", self._uri)
                return True
            else:
                logger.warning("RTSPSource: Failed to open RTSP stream '%s'", self._uri)
                self._is_open = False
                return False
        except Exception as exc:
            logger.error("RTSPSource: OpenCV exception opening RTSP '%s': %s", self._uri, exc)
            self._is_open = False
            return False

    def read_packet(self) -> Optional[StreamPacket]:
        if not self._is_open or self._cap is None:
            return None

        ret, frame = self._cap.read()
        if not ret or frame is None:
            return StreamPacket(payload=None, is_eof=True)

        self._packet_count += 1
        return StreamPacket(
            payload=frame,
            timestamp=time.time(),
            packet_index=self._packet_count,
            is_eof=False,
        )

    def close(self) -> None:
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None
        self._is_open = False
        logger.info("RTSPSource: Closed RTSP stream '%s'", self._uri)
