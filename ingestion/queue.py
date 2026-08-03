"""
Frame Queue Component.

Thread-safe Producer-Consumer Queue providing the primary frame transport channel
from the Ingestion Layer to the AI Processing Layer (Detector -> Tracker).
"""

from __future__ import annotations

import logging
import queue
from typing import Optional

from camera_analytics.ingestion.models import IngestedFrame

logger = logging.getLogger(__name__)


class FrameQueue:
    """Thread-safe Producer-Consumer Queue for pipeline frame transport."""

    def __init__(self, capacity: int = 30) -> None:
        if capacity < 1:
            raise ValueError("FrameQueue capacity must be at least 1.")
        self._capacity = capacity
        self._queue: queue.Queue[IngestedFrame] = queue.Queue(maxsize=capacity)
        self._drop_count = 0

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def drop_count(self) -> int:
        return self._drop_count

    def put(self, frame: IngestedFrame, timeout: float = 0.01) -> bool:
        """Enqueue a frame for AI processing (Producer).

        Args:
            frame: IngestedFrame instance.
            timeout: Max seconds to wait if queue is full.

        Returns:
            True if enqueued successfully, False if dropped due to queue full timeout.
        """
        try:
            self._queue.put(frame, block=True, timeout=timeout)
            return True
        except queue.Full:
            self._drop_count += 1
            logger.debug("FrameQueue: Full! Dropped frame #%d", frame.frame_number)
            return False

    def get(self, timeout: float = 0.1) -> Optional[IngestedFrame]:
        """Dequeue a frame for AI processing (Consumer).

        Args:
            timeout: Max seconds to wait for a frame.

        Returns:
            IngestedFrame if available, None if timeout reached.
        """
        try:
            return self._queue.get(block=True, timeout=timeout)
        except queue.Empty:
            return None

    def size(self) -> int:
        """Current number of queued frames."""
        return self._queue.qsize()

    def clear(self) -> None:
        """Clear all queued frames."""
        with self._queue.mutex:
            self._queue.queue.clear()
