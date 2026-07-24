"""
Folder/directory frame source.

Stub implementation of FrameSource for reading image files sequentially from a directory.
Defines standard lifecycle contract for image folder sources.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

import numpy as np

from camera_analytics.sources.base import FramePacket, FrameSource, SourceMetadata

if TYPE_CHECKING:
    from numpy.typing import NDArray

logger = logging.getLogger(__name__)


class FolderSource(FrameSource):
    """Frame source implementation for image file directories.

    Provides sequential reading from a folder containing image files (PNG, JPG, etc.).
    This is a stub implementation -- real image loading will be wired in Sprint 5.

    Args:
        folder_path: Path to the directory containing image files.
        fps: Simulated FPS for playback timestamp calculation.
    """

    def __init__(self, folder_path: str, fps: float = 30.0) -> None:
        self._folder_path = folder_path
        self._fps = fps
        self._is_open = False
        self._current_frame_id = 0
        self._total_frames = 50  # Default simulated total frames for stub
        self._resolution = (1920, 1080)

    @property
    def name(self) -> str:
        """Source name identifier."""
        return f"folder_source:{self._folder_path}"

    @property
    def is_open(self) -> bool:
        """Whether the image folder source is currently open."""
        return self._is_open

    @property
    def metadata(self) -> SourceMetadata:
        """Metadata for this image folder source."""
        return SourceMetadata(
            resolution=self._resolution,
            fps=self._fps,
            source_uri=self._folder_path,
            total_frames=self._total_frames,
            extra_info={"format": "image_folder"},
        )

    def open(self) -> None:
        """Open the image folder for reading."""
        if self._is_open:
            return

        self._is_open = True
        self._current_frame_id = 0
        logger.info("FolderSource opened: %s", self._folder_path)

    def read(self) -> Optional[FramePacket]:
        """Read the next frame packet from the image folder.

        Returns:
            FramePacket containing the frame, or None if all images are read.
        """
        if not self._is_open:
            return None

        if self._current_frame_id >= self._total_frames:
            logger.info("FolderSource finished reading all images: %s", self._folder_path)
            self.release()
            return None

        self._current_frame_id += 1
        timestamp = (self._current_frame_id - 1) / self._fps

        # Generate synthetic frame payload for stub
        blank_image: NDArray[np.uint8] = np.zeros(
            (self._resolution[1], self._resolution[0], 3), dtype=np.uint8
        )

        return FramePacket(
            frame_id=self._current_frame_id,
            timestamp=timestamp,
            image=blank_image,
            source_id=self.name,
        )

    def release(self) -> None:
        """Close the image folder handle."""
        if not self._is_open:
            return

        self._is_open = False
        logger.info("FolderSource released: %s", self._folder_path)
