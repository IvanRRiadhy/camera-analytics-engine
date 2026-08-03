"""
Abstract Video Decoder contract and DecoderFactory.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np

from camera_analytics.ingestion.sources.base import StreamPacket


class VideoDecoder(ABC):
    """Abstract Base Class for video frame decoders (OpenCV, FFmpeg, NVDEC)."""

    @abstractmethod
    def decode(self, packet: StreamPacket) -> np.ndarray:
        """Decode a StreamPacket into a NumPy NDArray image array (BGR/RGB).

        Args:
            packet: StreamPacket container object.

        Returns:
            Decoded NumPy NDArray image.

        Raises:
            ValueError: If frame decoding fails.
        """


class DecoderFactory:
    """Factory pattern for creating VideoDecoder instances by string name."""

    _decoders: dict[str, type[VideoDecoder]] = {}

    @classmethod
    def register(cls, name: str, decoder_cls: type[VideoDecoder]) -> None:
        cls._decoders[name.strip().lower()] = decoder_cls

    @classmethod
    def create(cls, name: str = "opencv") -> VideoDecoder:
        clean_name = name.strip().lower()
        if clean_name not in cls._decoders:
            raise KeyError(f"DecoderFactory: Unknown decoder type '{name}'. Registered: {list(cls._decoders.keys())}")
        return cls._decoders[clean_name]()
