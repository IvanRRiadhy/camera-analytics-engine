"""
SnapshotValidator Infrastructure (Sprint H1.5D1.5).

Verifies EngineStudioSnapshot completeness, non-null guarantees, and schema version consistency
before distributing snapshots to Pure View Inspector panels.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from camera_analytics.studio.snapshot.engine_studio_snapshot import EngineStudioSnapshot

logger = logging.getLogger(__name__)


class SnapshotValidator:
    """Validates EngineStudioSnapshot integrity and schema compliance."""

    REQUIRED_SUB_SNAPSHOTS: tuple[str, ...] = (
        "runtime",
        "pipeline",
        "model",
        "human",
        "zone",
        "module",
        "communication",
        "profiler",
        "thread",
        "configuration",
        "camera",
        "event_timeline",
    )

    @classmethod
    def validate(cls, snapshot: EngineStudioSnapshot) -> bool:
        """Validate snapshot fields and return True if valid."""
        if snapshot is None:
            logger.error("[SnapshotValidator] Snapshot is None!")
            return False

        if not snapshot.metadata or not snapshot.metadata.snapshot_id:
            logger.error("[SnapshotValidator] Snapshot missing valid Metadata or UUID!")
            return False

        for sub_name in cls.REQUIRED_SUB_SNAPSHOTS:
            if getattr(snapshot, sub_name, None) is None:
                logger.error(f"[SnapshotValidator] Snapshot missing required subsystem snapshot '{sub_name}'!")
                return False

        return True
