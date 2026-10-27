"""
Video file frame source.

Implementation of FrameSource for reading video files (MP4, AVI, MKV, etc.).
Uses OpenCV cv2.VideoCapture if file exists on disk, with fallback to synthetic frames.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

import numpy as np

from camera_analytics.sources.base import FramePacket, FrameSource, SourceMetadata

if TYPE_CHECKING:
    from numpy.typing import NDArray

logger = logging.getLogger(__name__)


class VideoSource(FrameSource):
    """Frame source implementation for reading video files.

    Provides frame-by-frame decoding from video files via OpenCV.
    If the specified file is not found, falls back gracefully to synthetic frames for testing.

    Args:
        file_path: Path to the video file.
        target_fps: Optional override for video playback FPS.
    """

    def __init__(
        self,
        file_path: str,
        target_fps: Optional[float] = None,
        backend_factory: Optional[Any] = None,
    ) -> None:
        self._file_path = file_path
        self._target_fps = target_fps
        self._backend_factory = backend_factory
        self._video_backend: Optional[Any] = None
        self._is_open = False
        self._current_frame_id = 0
        self._total_frames: Optional[int] = 100
        self._resolution = (1920, 1080)
        self._fps = target_fps if target_fps is not None else 30.0
        self._using_real_video = False

    @property
    def name(self) -> str:
        """Source name identifier."""
        return f"video_source:{self._file_path}"

    @property
    def is_open(self) -> bool:
        """Whether the video file source is currently open."""
        return self._is_open

    @property
    def metadata(self) -> SourceMetadata:
        """Metadata for this video file source."""
        return SourceMetadata(
            resolution=self._resolution,
            fps=self._fps,
            source_uri=self._file_path,
            total_frames=self._total_frames,
            extra_info={"format": "video_file", "real_video": self._using_real_video},
        )

    def open(self) -> None:
        """Open the video file for reading via IVideoBackend strategy."""
        if self._is_open:
            return

        self._current_frame_id = 0
        file_path_obj = Path(self._file_path)

        if file_path_obj.exists():
            try:
                from camera_analytics.platform.backend_factories import VideoBackendFactory
                factory = self._backend_factory or VideoBackendFactory()
                backend = factory.create_backend(str(file_path_obj))
                if backend.open(str(file_path_obj)):
                    self._video_backend = backend
                    self._using_real_video = True
                    logger.info("VideoSource opened video file via %s: '%s'", backend.__class__.__name__, self._file_path)
            except Exception as err:
                logger.warning("VideoBackend creation failed: %s. Falling back to synthetic frames.", err)
                self._using_real_video = False

        if not self._using_real_video:
            logger.info(
                "VideoSource file '%s' not found on disk. Using synthetic frames fallback.",
                self._file_path,
            )

        self._is_open = True

    def read(self) -> Optional[FramePacket]:
        """Read the next frame packet from the video file.

        Returns:
            FramePacket containing the frame, or None if EOF or closed.
        """
        if not self._is_open:
            return None

        # Real video decoding via IVideoBackend
        if self._using_real_video and self._video_backend is not None:
            ret, frame = self._video_backend.read_frame()
            if not ret or frame is None:
                logger.info("VideoSource reached EOF: %s", self._file_path)
                self.release()
                return None

            self._current_frame_id += 1
            timestamp = (self._current_frame_id - 1) / self._fps

            return FramePacket(
                frame_id=self._current_frame_id,
                timestamp=timestamp,
                image=frame,
                source_id=self.name,
            )

        # Fallback synthetic frame generation
        if self._total_frames is not None and self._current_frame_id >= self._total_frames:
            logger.info("VideoSource reached EOF: %s", self._file_path)
            self.release()
            return None

        self._current_frame_id += 1
        timestamp = (self._current_frame_id - 1) / self._fps

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
        """Close the video file stream."""
        if not self._is_open:
            return

        if self._video_backend is not None:
            try:
                self._video_backend.release()
            except Exception:
                pass
            self._video_backend = None

        self._is_open = False
        logger.info("VideoSource released: %s", self._file_path)
