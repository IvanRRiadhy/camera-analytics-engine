"""
SnapshotCache Infrastructure (Sprint H1.5D1.5).

Stores current_snapshot and previous_snapshot for trend comparison, configuration diffs, and replay support.
"""

from __future__ import annotations

import logging
from typing import Optional

from camera_analytics.studio.snapshot.engine_studio_snapshot import EngineStudioSnapshot

logger = logging.getLogger(__name__)


class SnapshotCache:
    """Bounded cache storing current and previous EngineStudioSnapshot instances."""

    def __init__(self, capacity: int = 2) -> None:
        self.capacity = capacity
        self.current_snapshot: Optional[EngineStudioSnapshot] = None
        self.previous_snapshot: Optional[EngineStudioSnapshot] = None

    def push(self, snapshot: EngineStudioSnapshot) -> None:
        """Push new snapshot into cache."""
        self.previous_snapshot = self.current_snapshot
        self.current_snapshot = snapshot

    def clear(self) -> None:
        """Clear cache contents."""
        self.current_snapshot = None
        self.previous_snapshot = None
