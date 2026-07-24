"""
Base interfaces and data structures for frame sources.

Defines:
    - SourceMetadata: Structured metadata about a frame source.
    - FramePacket: Immutable data packet carrying a single video frame and its context.
    - FrameSource: Abstract Port interface for all video/frame stream sources.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Iterator, Optional

import numpy as np

if TYPE_CHECKING:
    from numpy.typing import NDArray

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SourceMetadata:
    """Structured metadata about a frame source.

    Attributes:
        resolution: Frame size (width, height) in pixels.
        fps: Expected or configured frames per second.
        source_uri: Source identifier or path (e.g. RTSP URL, file path, device index).
        total_frames: Total number of frames if known (e.g. for video files/folders), else None.
        extra_info: Additional source-specific key-value information.
    """

    resolution: tuple[int, int]
    fps: float
    source_uri: str
    total_frames: Optional[int] = None
    extra_info: dict[str, Any] = field(default_factory=dict)

    @property
    def width(self) -> int:
        """Frame width in pixels."""
        return self.resolution[0]

    @property
    def height(self) -> int:
        """Frame height in pixels."""
        return self.resolution[1]


@dataclass(frozen=True, slots=True)
class FramePacket:
    """Immutable data container carrying a single frame from a FrameSource.

    Attributes:
        frame_id: Sequential frame counter assigned by the source (1-indexed).
        timestamp: Elapsed timestamp in seconds from stream start or video PTS.
        image: Frame payload as a BGR uint8 numpy array (HxWx3).
        source_id: Identifier of the source that produced this packet.
    """

    frame_id: int
    timestamp: float
    image: NDArray[np.uint8]
    source_id: str

    @property
    def shape(self) -> tuple[int, ...]:
        """Shape of the image numpy array (height, width, channels)."""
        return self.image.shape


class FrameSource(ABC):
    """Abstract interface for all frame sources (Input Port).

    Defines a unified lifecycle and interface for frame ingestion across
    different sources (Video files, RTSP streams, USB webcams, Folders).

    Standard Lifecycle::

        source = SomeSource(...)
        source.open()
        try:
            while source.is_open:
                packet = source.read()
                if packet is None:
                    break
                # Process packet
        finally:
            source.release()

    Or via Iterator / Context Manager::

        with SomeSource(...) as source:
            for packet in source:
                # Process packet
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable identifier of this source instance."""

    @property
    @abstractmethod
    def is_open(self) -> bool:
        """Whether the source is currently open and active."""

    @property
    @abstractmethod
    def metadata(self) -> SourceMetadata:
        """Metadata describing this frame source."""

    @abstractmethod
    def open(self) -> None:
        """Open the connection, file, or device.

        Raises:
            RuntimeError: If opening fails.
        """

    @abstractmethod
    def read(self) -> Optional[FramePacket]:
        """Read and return the next FramePacket from the source.

        Returns:
            The next FramePacket, or None if stream ends or is unreadable.
        """

    @abstractmethod
    def release(self) -> None:
        """Close connection and release underlying resources."""

    def __iter__(self) -> Iterator[FramePacket]:
        """Yield FramePackets sequentially until stream ends or closes."""
        if not self.is_open:
            self.open()

        while self.is_open:
            packet = self.read()
            if packet is None:
                break
            yield packet

    def __enter__(self) -> FrameSource:
        if not self.is_open:
            self.open()
        return self

    def __exit__(
        self,
        exc_type: type | None,
        exc_val: Exception | None,
        exc_tb: object,
    ) -> None:
        self.release()
