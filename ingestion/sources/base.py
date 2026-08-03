"""
Abstract VideoSource contract with backend-agnostic StreamPacket container.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True, slots=True)
class StreamPacket:
    """Backend-neutral container for encoded or raw video packet payloads.

    Decouples VideoSource from specific decoders (OpenCV, FFmpeg, GStreamer, NVDEC).

    Attributes:
        payload: Raw frame buffer / packet payload object (e.g. cv2 frame, ffmpeg AVPacket, bytes).
        timestamp: Packet capture timestamp.
        packet_index: Sequential packet integer index.
        is_eof: Whether this packet signals end-of-stream.
        is_keyframe: Whether packet is an I-Frame / Keyframe (if known).
        metadata: Transport or packet metadata dictionary.
    """

    payload: Any
    timestamp: float = field(default_factory=time.time)
    packet_index: int = 0
    is_eof: bool = False
    is_keyframe: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


class VideoSource(ABC):
    """Abstract Base Class for all video stream input sources."""

    def __init__(self, uri: str, params: Optional[dict[str, Any]] = None) -> None:
        self._uri = uri
        self._params = params or {}
        self._is_open = False

    @property
    def uri(self) -> str:
        """Stream or resource URI."""
        return self._uri

    @property
    def is_open(self) -> bool:
        """Whether source stream is open."""
        return self._is_open

    @abstractmethod
    def open(self) -> bool:
        """Open the video stream source.

        Returns:
            True if opened successfully, False otherwise.
        """

    @abstractmethod
    def read_packet(self) -> Optional[StreamPacket]:
        """Fetch the next StreamPacket from the source.

        Returns:
            StreamPacket instance, or None if stream error/EOF.
        """

    @abstractmethod
    def close(self) -> None:
        """Close stream source and release native resources."""
