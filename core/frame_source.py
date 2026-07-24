"""
Frame source interfaces and fake implementations.

Defines the abstract FrameSource port for video/frame ingestion and
a synthetic FakeFrameSource implementation for testing without real
cameras or video files.

Example::

    source = FakeFrameSource(total_frames=100, width=1920, height=1080)
    for frame in source:
        print(frame.shape)
    source.release()
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Iterator

import numpy as np

if TYPE_CHECKING:
    from numpy.typing import NDArray

logger = logging.getLogger(__name__)


class FrameSource(ABC):
    """Abstract interface for video frame sources.

    All video stream sources (RTSP, video files, USB webcams, synthetic sources)
    implement this interface. The Runner consumes frames from a FrameSource
    and feeds them through the detection -> tracking -> pipeline execution loop.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Name or identifier of the frame source."""

    @abstractmethod
    def __iter__(self) -> Iterator[NDArray[np.uint8]]:
        """Yield video frames sequentially as uint8 BGR numpy arrays."""

    @abstractmethod
    def release(self) -> None:
        """Release underlying resources (open video files, RTSP connections, etc.)."""

    def __enter__(self) -> FrameSource:
        return self

    def __exit__(self, exc_type: type | None, exc_val: Exception | None, exc_tb: object) -> None:
        self.release()


class FakeFrameSource(FrameSource):
    """Synthetic frame source producing blank video frames.

    Generates blank numpy arrays of specified resolution and frame count.
    Used for unit testing and demo runs without requiring video files.

    Args:
        total_frames: Number of frames to generate before stopping.
        width: Frame width in pixels.
        height: Frame height in pixels.
    """

    def __init__(
        self,
        total_frames: int = 20,
        width: int = 1920,
        height: int = 1080,
    ) -> None:
        self._total_frames = total_frames
        self._width = width
        self._height = height
        self._current_frame = 0

    @property
    def name(self) -> str:
        return "fake_frame_source"

    @property
    def total_frames(self) -> int:
        return self._total_frames

    def __iter__(self) -> Iterator[NDArray[np.uint8]]:
        """Yield blank BGR frames."""
        self._current_frame = 0
        blank_frame = np.zeros((self._height, self._width, 3), dtype=np.uint8)

        while self._current_frame < self._total_frames:
            self._current_frame += 1
            yield blank_frame.copy()

    def release(self) -> None:
        """Release fake source resources."""
        self._current_frame = self._total_frames
        logger.info("FakeFrameSource released")
