"""
Ingested Frame and Metrics Domain Models.

Defines immutable `IngestedFrame` (with writeable=False numpy array) and `IngestionMetrics`.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np


@dataclass(frozen=True, slots=True)
class IngestedFrame:
    """Immutable Video Frame domain representation.

    Attributes:
        frame_id: Unique string frame identifier.
        pipeline_id: Unique pipeline identifier.
        camera_id: Unique camera identifier.
        frame_number: Sequential integer frame number.
        timestamp: UTC epoch timestamp of frame read.
        read_latency_ms: Time taken to read and decode frame in milliseconds.
        image: Read-only NumPy NDArray representing the image (BGR/YUV).
        width: Frame width in pixels.
        height: Frame height in pixels.
        channels: Color channels count (3 for BGR).
        metadata: Custom metadata dictionary.
    """

    pipeline_id: str
    camera_id: str
    frame_number: int
    timestamp: float
    read_latency_ms: float
    image: np.ndarray = field(repr=False)
    width: int
    height: int
    channels: int = 3
    frame_id: str = field(default_factory=lambda: f"frame_{uuid.uuid4().hex[:10]}")
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Ensure image numpy array is immutable (zero-copy pass-through safety)."""
        if isinstance(self.image, np.ndarray):
            self.image.flags.writeable = False


@dataclass
class IngestionMetrics:
    """Performance and health monitoring metrics for a Video Ingestion Worker."""

    fps_input: float = 0.0
    total_frames_read: int = 0
    frame_drop_count: int = 0
    reconnect_count: int = 0
    last_frame_timestamp: float = 0.0
    avg_read_latency_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "fps_input": round(self.fps_input, 1),
            "total_frames_read": self.total_frames_read,
            "frame_drop_count": self.frame_drop_count,
            "reconnect_count": self.reconnect_count,
            "last_frame_timestamp": round(self.last_frame_timestamp, 3),
            "avg_read_latency_ms": round(self.avg_read_latency_ms, 2),
        }
