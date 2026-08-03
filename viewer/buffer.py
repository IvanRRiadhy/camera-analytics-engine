"""
Presentation Frame Buffer Component.

Thread-safe ring buffer cache storing the latest completed FramePresentation produced by PipelineExecutionWorker.
"""

from __future__ import annotations

import logging
import threading
from collections import deque
from typing import Optional

from camera_analytics.viewer.models import FramePresentation

logger = logging.getLogger(__name__)


class PresentationFrameBuffer:
    """Thread-safe ring cache storing the latest FramePresentation for UI Viewers."""

    def __init__(self, capacity: int = 5) -> None:
        self._capacity = capacity
        self._buffer: deque[FramePresentation] = deque(maxlen=capacity)
        self._lock = threading.Lock()

    def update(self, presentation: FramePresentation) -> None:
        """Push a newly completed FramePresentation into the buffer.

        Args:
            presentation: FramePresentation view model instance.
        """
        with self._lock:
            self._buffer.append(presentation)

    def get_latest(self) -> Optional[FramePresentation]:
        """Retrieve the latest FramePresentation view model without removing it.

        Returns:
            Latest FramePresentation or None if buffer is empty.
        """
        with self._lock:
            return self._buffer[-1] if self._buffer else None

    def clear(self) -> None:
        """Clear all buffered presentations."""
        with self._lock:
            self._buffer.clear()
