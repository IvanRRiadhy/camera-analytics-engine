"""
RTSP Video Source implementation.
"""

from __future__ import annotations

import logging
import socket
import time
from typing import Any, Optional
from urllib.parse import urlsplit

import cv2

from camera_analytics.ingestion.sources.base import StreamPacket, VideoSource

logger = logging.getLogger(__name__)


class RTSPSource(VideoSource):
    """VideoSource implementation for network RTSP streams."""

    def __init__(self, uri: str, params: Optional[dict[str, Any]] = None) -> None:
        super().__init__(uri=uri, params=params)
        self._cap: Optional[cv2.VideoCapture] = None
        self._packet_count = 0
        p = self._params
        self._open_timeout_sec = float(
            p.get("open_timeout_sec", p.get("rtsp_open_timeout_sec", p.get("connect_timeout_sec", 5.0)))
        )
        self._read_timeout_sec = float(
            p.get("read_timeout_sec", p.get("rtsp_read_timeout_sec", 5.0))
        )
        self._tcp_precheck_timeout_sec = float(p.get("tcp_precheck_timeout_sec", 2.0))

    def _tcp_precheck(self) -> bool:
        """Perform a fast TCP socket reachability check before invoking FFmpeg."""
        try:
            parsed = urlsplit(self._uri)
            host = parsed.hostname
            if not host:
                return True
            scheme = (parsed.scheme or "rtsp").lower()
            default_port = 322 if scheme == "rtsps" else (443 if scheme == "https" else (80 if scheme == "http" else 554))
            port = parsed.port or default_port
        except Exception:
            return True

        t0 = time.perf_counter()
        try:
            with socket.create_connection((host, port), timeout=self._tcp_precheck_timeout_sec):
                return True
        except OSError as exc:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            logger.warning(
                "RTSPSource: TCP pre-check failed for '%s' (%s:%s, timeout=%.1fs, elapsed=%.0fms): %s",
                self._uri,
                host,
                port,
                self._tcp_precheck_timeout_sec,
                elapsed_ms,
                exc,
            )
            return False

    def open(self) -> bool:
        if self._is_open and self._cap is not None:
            return True

        if not self._tcp_precheck():
            self._is_open = False
            return False

        open_timeout_ms = int(self._open_timeout_sec * 1000)
        read_timeout_ms = int(self._read_timeout_sec * 1000)
        try:
            self._cap = cv2.VideoCapture(
                self._uri,
                cv2.CAP_FFMPEG,
                [
                    cv2.CAP_PROP_OPEN_TIMEOUT_MSEC,
                    open_timeout_ms,
                    cv2.CAP_PROP_READ_TIMEOUT_MSEC,
                    read_timeout_ms,
                ],
            )
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
