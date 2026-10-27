"""
Webcam (USB / UVC Device) Video Source implementation.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

import cv2

from camera_analytics.ingestion.sources.base import StreamPacket, VideoSource

logger = logging.getLogger(__name__)


class WebcamSource(VideoSource):
    """VideoSource implementation for local USB and UVC webcams using integer device indexes."""

    def __init__(self, uri: str, params: Optional[dict[str, Any]] = None) -> None:
        super().__init__(uri=uri, params=params)
        self._cap: Optional[cv2.VideoCapture] = None
        self._packet_count = 0
        
        # Parse device index from URI, e.g. "webcam://0", "webcam:0", "0"
        clean_str = str(uri).lower().replace("webcam://", "").replace("webcam:", "").strip()
        try:
            self._device_index = int(clean_str)
        except ValueError:
            logger.warning("WebcamSource: Unable to parse integer index from '%s', defaulting to 0", uri)
            self._device_index = 0

    def open(self) -> bool:
        if self._is_open and self._cap is not None:
            return True

        try:
            logger.info("WebcamSource: Attempting to open USB/UVC camera index %d", self._device_index)
            # Use CAP_DSHOW on Windows for fast initialization if available
            self._cap = cv2.VideoCapture(self._device_index, cv2.CAP_DSHOW)
            if not self._cap.isOpened():
                # Fallback to default backend
                self._cap = cv2.VideoCapture(self._device_index)

            if self._cap.isOpened():
                # Apply custom camera parameters if provided
                if self._params:
                    if "width" in self._params:
                        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, int(self._params["width"]))
                    if "height" in self._params:
                        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(self._params["height"]))
                    if "fps" in self._params:
                        self._cap.set(cv2.CAP_PROP_FPS, int(self._params["fps"]))

                self._is_open = True
                logger.info("WebcamSource: Successfully opened webcam index %d", self._device_index)
                return True
            else:
                logger.warning("WebcamSource: Failed to open webcam index %d", self._device_index)
                self._is_open = False
                return False
        except Exception as exc:
            logger.error("WebcamSource: Exception opening webcam index %d: %s", self._device_index, exc)
            self._is_open = False
            return False

    def read_packet(self) -> Optional[StreamPacket]:
        if not self._is_open or self._cap is None:
            return None

        ret, frame = self._cap.read()
        if not ret or frame is None:
            return None

        self._packet_count += 1
        now = time.time()
        return StreamPacket(
            payload=frame,
            timestamp=now,
            packet_index=self._packet_count,
            is_eof=False,
            is_keyframe=True,
            metadata={
                "source_type": "webcam",
                "device_index": self._device_index,
                "width": frame.shape[1],
                "height": frame.shape[0],
            },
        )

    def close(self) -> None:
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception as exc:
                logger.debug("WebcamSource: Exception releasing VideoCapture: %s", exc)
            finally:
                self._cap = None
        self._is_open = False
        logger.info("WebcamSource: Closed webcam index %d", self._device_index)

    def get_fps(self) -> float:
        if self._cap is not None:
            fps = float(self._cap.get(cv2.CAP_PROP_FPS))
            if fps > 0.0:
                return fps
        return 30.0
