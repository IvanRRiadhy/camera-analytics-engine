"""
Overlay Store Component.

Thread-safe storage holding the latest visual overlays (boxes, tracks, metrics)
per pipeline without image data, enabling decoupled display rendering.
"""

from __future__ import annotations

import logging
import threading
from typing import Optional

from camera_analytics.viewer.models import OverlayData

logger = logging.getLogger(__name__)


class OverlayStore:
    """Thread-safe store for per-pipeline visual overlays."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._overlays: dict[str, OverlayData] = {}

    def publish(self, pipeline_id: str, overlay: OverlayData) -> None:
        """Publish the latest overlay for a pipeline."""
        with self._lock:
            self._overlays[pipeline_id] = overlay

    def get_latest(self, pipeline_id: str) -> Optional[OverlayData]:
        """Retrieve the newest overlay for a pipeline."""
        with self._lock:
            return self._overlays.get(pipeline_id)

    def clear(self, pipeline_id: Optional[str] = None) -> None:
        """Clear overlays."""
        with self._lock:
            if pipeline_id is not None:
                self._overlays.pop(pipeline_id, None)
            else:
                self._overlays.clear()

