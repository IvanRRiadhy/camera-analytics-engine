"""
Frame Buffer Component.

Thread-safe bounded Ring Buffer acting as a latest-frame cache for viewer, debugging,
and status snapshot access without interfering with the AI processing pipeline.
"""

from __future__ import annotations

import collections
import logging
import threading
from typing import Optional

from camera_analytics.ingestion.models import IngestedFrame

logger = logging.getLogger(__name__)


class FrameBuffer:
    """Thread-safe Bounded Ring Buffer cache for live video frames.

    Designed specifically as a latest-frame cache for UI viewers, debugging tools,
    and diagnostic snapshots. Automatically overwrites the oldest frame when full.
    """

    def __init__(self, capacity: int = 30) -> None:
        if capacity < 1:
            raise ValueError("FrameBuffer capacity must be at least 1.")
        self._capacity = capacity
        self._buffer: collections.deque[IngestedFrame] = collections.deque(maxlen=capacity)
        self._lock = threading.Lock()
        self._overflow_count = 0

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def overflow_count(self) -> int:
        return self._overflow_count

    def push(self, frame: IngestedFrame) -> bool:
        """Push a frame into the buffer cache. Overwrites oldest frame if capacity reached.

        Returns:
            True if pushed cleanly, False if an overwrite occurred.
        """
        with self._lock:
            overwrote = len(self._buffer) >= self._capacity
            if overwrote:
                self._overflow_count += 1

            self._buffer.append(frame)
            return not overwrote

    def pop(self) -> Optional[IngestedFrame]:
        """Pop the oldest frame from the buffer cache."""
        with self._lock:
            if len(self._buffer) == 0:
                return None
            return self._buffer.popleft()

    def get_latest(self) -> Optional[IngestedFrame]:
        """Peek at the most recently ingested frame without removing it (for UI viewers)."""
        with self._lock:
            if len(self._buffer) == 0:
                return None
            return self._buffer[-1]

    def snapshot(self) -> list[IngestedFrame]:
        """Return a snapshot list of all current frames in the cache."""
        with self._lock:
            return list(self._buffer)

    def clear(self) -> None:
        """Clear all frames in buffer cache."""
        with self._lock:
            self._buffer.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._buffer)
