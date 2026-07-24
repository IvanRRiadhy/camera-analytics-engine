"""
RTSP live stream frame source implementation.

Provides robust, non-blocking frame reading from network RTSP IP cameras via OpenCV/FFMPEG.
Enforces TCP transport, auto-reconnection logic on network drop, connection timeout handling,
and graceful shutdown without crashing.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import TYPE_CHECKING, Any, Optional

import numpy as np

from camera_analytics.sources.base import FramePacket, FrameSource, SourceMetadata

if TYPE_CHECKING:
    from numpy.typing import NDArray

logger = logging.getLogger(__name__)


class RTSPSource(FrameSource):
    """Frame source implementation for live RTSP network video streams.

    Features:
        - Threaded background frame capture to prevent pipeline blocking.
        - Enforced TCP transport (`rtsp_transport;tcp`).
        - Automatic reconnection retries on connection loss.
        - Reconnect count and frame drop tracking.
        - Graceful resource cleanup on release.

    Args:
        rtsp_url: Connection URL for RTSP camera stream (e.g. 'rtsp://user:pass@192.168.1.100:554/stream').
        reconnect_delay: Delay in seconds between reconnection retries.
        buffer_size: OpenCV buffer size.
        timeout_sec: Connection timeout threshold in seconds.
        target_fps: Optional target FPS override.
    """

    def __init__(
        self,
        rtsp_url: str,
        reconnect_delay: float = 3.0,
        buffer_size: int = 1,
        timeout_sec: float = 10.0,
        target_fps: Optional[float] = None,
    ) -> None:
        self._rtsp_url = rtsp_url
        self._reconnect_delay = reconnect_delay
        self._buffer_size = buffer_size
        self._timeout_sec = timeout_sec
        self._target_fps = target_fps

        self._is_open = False
        self._current_frame_id = 0
        self._start_time = 0.0
        self._resolution = (1920, 1080)
        self._fps = target_fps if target_fps is not None else 30.0

        # Threading and stream state
        self._cap: Any = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

        self._latest_frame: Optional[NDArray[np.uint8]] = None
        self._latest_timestamp: float = 0.0
        self._last_read_time: float = 0.0

        # Statistics
        self._reconnect_count = 0
        self._dropped_frames = 0
        self._using_synthetic_fallback = False

    @property
    def name(self) -> str:
        """Source name identifier."""
        return f"rtsp_source:{self._rtsp_url}"

    @property
    def is_open(self) -> bool:
        """Whether the RTSP stream is currently connected and active."""
        return self._is_open

    @property
    def reconnect_count(self) -> int:
        """Total number of successful reconnections performed."""
        return self._reconnect_count

    @property
    def dropped_frames(self) -> int:
        """Total number of dropped/skipped frames."""
        return self._dropped_frames

    @property
    def metadata(self) -> SourceMetadata:
        """Metadata for this RTSP stream source."""
        return SourceMetadata(
            resolution=self._resolution,
            fps=self._fps,
            source_uri=self._rtsp_url,
            total_frames=None,  # Unbounded live stream
            extra_info={
                "format": "rtsp_live_stream",
                "transport": "tcp",
                "reconnect_count": self._reconnect_count,
                "dropped_frames": self._dropped_frames,
            },
        )

    def open(self) -> None:
        """Connect to the RTSP stream and start background reader thread."""
        if self._is_open:
            return

        self._stop_event.clear()
        self._start_time = time.monotonic()
        self._last_read_time = time.monotonic()

        # Enforce TCP transport for RTSP in FFMPEG/OpenCV environment
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"

        if self._connect_stream():
            self._is_open = True
            self._thread = threading.Thread(
                target=self._reader_loop, daemon=True, name="RTSPSourceReader"
            )
            self._thread.start()
            logger.info("RTSPSource connected successfully: %s", self._rtsp_url)
        else:
            logger.warning(
                "RTSPSource initial connection failed for '%s'. Starting background reconnect thread...",
                self._rtsp_url,
            )
            self._is_open = True
            self._using_synthetic_fallback = True
            self._thread = threading.Thread(
                target=self._reader_loop, daemon=True, name="RTSPSourceReader"
            )
            self._thread.start()

    def read(self) -> Optional[FramePacket]:
        """Read the next available frame packet from the RTSP stream.

        Returns:
            FramePacket containing the frame, or None if stopped.
        """
        if not self._is_open or self._stop_event.is_set():
            return None

        with self._lock:
            frame = self._latest_frame.copy() if self._latest_frame is not None else None
            timestamp = self._latest_timestamp

        if frame is None:
            # Generate synthetic placeholder if stream is connecting
            frame = np.zeros((self._resolution[1], self._resolution[0], 3), dtype=np.uint8)
            timestamp = time.monotonic() - self._start_time

        self._current_frame_id += 1

        return FramePacket(
            frame_id=self._current_frame_id,
            timestamp=timestamp,
            image=frame,
            source_id=self.name,
        )

    def release(self) -> None:
        """Gracefully disconnect and release RTSP stream resources."""
        if not self._is_open:
            return

        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

        with self._lock:
            if self._cap is not None:
                try:
                    self._cap.release()
                except Exception:
                    pass
                self._cap = None
            self._latest_frame = None

        self._is_open = False
        logger.info("RTSPSource released cleanly: %s", self._rtsp_url)

    # --- Internal Stream Capture & Reconnect Logic ---

    def _connect_stream(self) -> bool:
        """Attempt to open OpenCV VideoCapture stream via TCP."""
        try:
            import cv2
            cap = cv2.VideoCapture(self._rtsp_url, cv2.CAP_FFMPEG)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, self._buffer_size)

            if cap.isOpened():
                ret, frame = cap.read()
                if ret and frame is not None:
                    h, w = frame.shape[:2]
                    self._resolution = (w, h)
                    video_fps = cap.get(cv2.CAP_PROP_FPS)
                    if self._target_fps is None and video_fps > 0:
                        self._fps = float(video_fps)

                    self._cap = cap
                    self._using_synthetic_fallback = False
                    with self._lock:
                        self._latest_frame = frame
                        self._latest_timestamp = time.monotonic() - self._start_time
                    logger.info("RTSP Connected (%dx%d @ %.1f FPS)", w, h, self._fps)
                    return True

            if cap is not None:
                cap.release()
        except Exception as exc:
            logger.warning("RTSP Stream connection error (%s)", exc)

        return False

    def _reader_loop(self) -> None:
        """Background thread loop that continuously reads frames and handles auto-reconnect."""
        import cv2

        while not self._stop_event.is_set():
            if self._cap is None or not self._cap.isOpened() or self._using_synthetic_fallback:
                logger.info("Reconnect Started: attempting connection to '%s'", self._rtsp_url)
                if self._connect_stream():
                    self._reconnect_count += 1
                    logger.info("Reconnect Success (#%d) for '%s'", self._reconnect_count, self._rtsp_url)
                else:
                    logger.warning("Reconnect Failed for '%s'. Retrying in %.1fs...",
                                   self._rtsp_url, self._reconnect_delay)
                    time.sleep(self._reconnect_delay)
                    continue

            # Read frame from stream
            ret, frame = self._cap.read()
            now = time.monotonic()

            if ret and frame is not None:
                self._last_read_time = now
                with self._lock:
                    self._latest_frame = frame
                    self._latest_timestamp = now - self._start_time
            else:
                self._dropped_frames += 1
                if (now - self._last_read_time) > 1.0:
                    logger.warning("Frame Drop detected on RTSP stream (stall %.1fs, total drops: %d)",
                                   now - self._last_read_time, self._dropped_frames)

                if (now - self._last_read_time) > self._timeout_sec:
                    logger.error("RTSP Stream timeout (>%.1fs). Re-establishing connection...", self._timeout_sec)
                    logger.info("RTSP Disconnected: %s", self._rtsp_url)
                    with self._lock:
                        if self._cap:
                            self._cap.release()
                            self._cap = None
                    self._using_synthetic_fallback = True

            time.sleep(0.005)  # Yield CPU execution
