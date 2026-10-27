"""
Bounded Ring Buffer HumanTimeline Infrastructure (Sprint H1.5C).

Provides high-performance temporal inference event buffering for tracked persons.
Utilizes collections.deque(maxlen=N) to guarantee constant O(1) memory bounds and automatic pruning.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Iterator, Optional, Sequence

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class HumanTimelineEntry:
    """Bounded temporal entry recording a single inference event with full provenance."""

    timestamp_utc: float
    frame_index: int
    capability_id: str
    value: Any
    confidence: float = 1.0
    quality_score: float = 1.0
    latency_ms: float = 0.0
    module_id: str = "unknown"
    camera_id: str = "default_camera"
    pipeline_id: str = "default_pipeline"
    raw_outputs: dict[str, Any] = field(default_factory=dict)


class HumanTimeline:
    """Ring buffer timeline storing recent inference events for a single tracked person."""

    def __init__(self, max_entries: int = 100, max_age_seconds: float = 60.0) -> None:
        self.max_entries = max_entries
        self.max_age_seconds = max_age_seconds
        self._entries: deque[HumanTimelineEntry] = deque(maxlen=max_entries)

    def append(self, entry: HumanTimelineEntry) -> None:
        """Append a new timeline entry to the ring buffer."""
        self._entries.append(entry)
        self.prune_expired()

    def prune_expired(self) -> None:
        """Remove entries exceeding max_age_seconds."""
        now = time.time()
        while self._entries and (now - self._entries[0].timestamp_utc) > self.max_age_seconds:
            self._entries.popleft()

    def get_entries(self, capability_id: Optional[str] = None) -> list[HumanTimelineEntry]:
        """Return list of active timeline entries, optionally filtered by capability_id."""
        self.prune_expired()
        if capability_id:
            return [e for e in self._entries if e.capability_id == capability_id]
        return list(self._entries)

    def __len__(self) -> int:
        return len(self._entries)

    def __iter__(self) -> Iterator[HumanTimelineEntry]:
        return iter(self._entries)

    def clear(self) -> None:
        """Clear all timeline entries."""
        self._entries.clear()
