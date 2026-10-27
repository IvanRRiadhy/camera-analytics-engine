"""
Human State Cache.

Thread-safe per-pipeline cache managing the lifecycle, persistence, and eviction of
HumanState profiles for active track IDs.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Optional

from camera_analytics.core.human.models import HumanState

logger = logging.getLogger(__name__)


class HumanStateCache:
    """Thread-safe per-pipeline cache mapping track_id to HumanState."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._cache: dict[int, HumanState] = {}

    def get(self, track_id: int) -> Optional[HumanState]:
        """Retrieve HumanState for track_id if present."""
        with self._lock:
            return self._cache.get(track_id)

    def get_or_create(self, track_id: int) -> HumanState:
        """Get existing HumanState or initialize a default state for track_id."""
        with self._lock:
            if track_id not in self._cache:
                self._cache[track_id] = HumanState(track_id=track_id)
            return self._cache[track_id]

    def update(self, state: HumanState) -> None:
        """Update or overwrite HumanState entry in cache."""
        with self._lock:
            self._cache[state.track_id] = state

    def evict(self, track_id: int) -> Optional[HumanState]:
        """Remove and return HumanState entry when track terminates."""
        with self._lock:
            return self._cache.pop(track_id, None)

    def purge_expired(self, active_track_ids: set[int]) -> list[int]:
        """Purge all cached track states that are no longer active."""
        evicted_ids: list[int] = []
        with self._lock:
            cached_ids = list(self._cache.keys())
            for t_id in cached_ids:
                if t_id not in active_track_ids:
                    del self._cache[t_id]
                    evicted_ids.append(t_id)

        if evicted_ids:
            logger.debug("[HumanStateCache] Purged %d expired tracks: %s", len(evicted_ids), evicted_ids)
        return evicted_ids

    def get_all_states(self) -> dict[int, HumanState]:
        """Return a shallow copy of all cached human states."""
        with self._lock:
            return dict(self._cache)

    def clear(self) -> None:
        """Purge all entries from the cache."""
        with self._lock:
            self._cache.clear()
