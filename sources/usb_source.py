"""
USB webcam frame source.

Stub implementation of FrameSource for local USB webcams / hardware capture devices.
Defines standard lifecycle contract for USB camera devices.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Optional

import numpy as np

from camera_analytics.sources.base import FramePacket, FrameSource, SourceMetadata

if TYPE_CHECKING:
    from numpy.typing import NDArray

logger = logging.getLogger(__name__)


class USBCameraSource(FrameSource):
    """Frame source implementation for local USB webcams.

    Provides frame reading from local hardware camera devices by index.
    This is a stub implementation -- real V4L2/DirectShow capture will be wired in Sprint 5.

    Args:
        device_index: Local camera index (e.g. 0 for /dev/video0 or default webcam).
        resolution: Requested capture resolution tuple (width, height).
        fps: Requested capture FPS.
    """

    def __init__(
        self,
        device_index: int = 0,
        resolution: tuple[int, int] = (1920, 1080),
        fps: float = 30.0,
    ) -> None:
        self._device_index = device_index
        self._resolution = resolution
        self._fps = fps
        self._is_open = False
        self._current_frame_id = 0
        self._start_time = 0.0

    @property
    def name(self) -> str:
        """Source name identifier."""
        return f"usb_source:dev_{self._device_index}"

    @property
    def is_open(self) -> bool:
        """Whether the USB camera device is currently open."""
        return self._is_open

    @property
    def metadata(self) -> SourceMetadata:
        """Metadata for this USB camera source."""
        return SourceMetadata(
            resolution=self._resolution,
            fps=self._fps,
            source_uri=str(self._device_index),
            total_frames=None,  # Live camera has unbounded frame count
            extra_info={"format": "usb_webcam", "device_index": self._device_index},
        )

    def open(self) -> None:
        """Open the USB camera device."""
        if self._is_open:
            return

        self._is_open = True
        self._current_frame_id = 0
        self._start_time = time.monotonic()
        logger.info("USBCameraSource opened (device_index=%d)", self._device_index)

    def read(self) -> Optional[FramePacket]:
        """Read the next frame packet from the USB camera.

        Returns:
            FramePacket containing the frame, or None if device errors.
        """
        if not self._is_open:
            return None

        self._current_frame_id += 1
        elapsed = time.monotonic() - self._start_time

        # Generate synthetic frame payload for stub
        blank_image: NDArray[np.uint8] = np.zeros(
            (self._resolution[1], self._resolution[0], 3), dtype=np.uint8
        )

        return FramePacket(
            frame_id=self._current_frame_id,
            timestamp=elapsed,
            image=blank_image,
            source_id=self.name,
        )

    def release(self) -> None:
        """Release the USB camera device handle."""
        if not self._is_open:
            return

        self._is_open = False
        logger.info("USBCameraSource released (device_index=%d)", self._device_index)
