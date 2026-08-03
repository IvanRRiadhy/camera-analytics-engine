"""
Frame Ingestion Adapter Component.

Converts Sprint 11.3 IngestedFrame domain instances into Sprint 1-10 FrameEntity and FrameContext structures.
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np

from camera_analytics.entities.models import FrameEntity
from camera_analytics.ingestion.models import IngestedFrame

logger = logging.getLogger(__name__)


class FrameIngestionAdapter:
    """Adapter transforming IngestedFrame objects into legacy FrameEntity representations."""

    @staticmethod
    def to_frame_entity(frame: IngestedFrame) -> FrameEntity:
        """Convert IngestedFrame to FrameEntity.

        Args:
            frame: IngestedFrame instance from Video Ingestion Layer.

        Returns:
            FrameEntity dataclass instance.
        """
        return FrameEntity(
            frame_index=frame.frame_number,
            timestamp=frame.timestamp,
            frame_width=frame.width,
            frame_height=frame.height,
            fps=30.0,
            latency_ms=frame.read_latency_ms,
        )

    @staticmethod
    def extract_image(frame: IngestedFrame) -> np.ndarray:
        """Extract image array as a writeable copy if modification is required by visualizers.

        Args:
            frame: IngestedFrame instance.

        Returns:
            NumPy NDArray image copy.
        """
        return frame.image.copy()
