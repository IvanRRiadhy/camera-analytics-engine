"""
Typed Snapshot Builder Component (Sprint 4A).

Pure serializer constructing immutable CameraAnalyticsSnapshot objects.
Does not contain plugin-specific business logic.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from camera_analytics.runtime.analytics.health_monitor import HealthMonitor
from camera_analytics.runtime.analytics.models import (
    CameraAnalyticsSnapshot,
    GenericPluginState,
    LoiteringState,
    PeopleCountingState,
    QueueDetectionState,
    ZoneOccupancyState,
)
from camera_analytics.runtime.analytics.repository import PluginStateRepository

logger = logging.getLogger(__name__)


class SnapshotBuilder:
    """Pure Builder producing immutable strongly typed CameraAnalyticsSnapshot objects."""

    @staticmethod
    def build_snapshot(
        camera_id: str,
        pipeline_id: str,
        repository: PluginStateRepository,
        health_monitor: HealthMonitor,
        generic_plugin_states: Optional[Dict[str, GenericPluginState]] = None,
        worker: Optional[Any] = None,
        context: Optional[Any] = None,
    ) -> CameraAnalyticsSnapshot:
        now_iso = datetime.now(timezone.utc).isoformat()
        health_state = health_monitor.collect_health(worker=worker, context=context)

        # Legacy typed states for backward compatibility
        people_st = repository.get_state("peopleCounting", PeopleCountingState)
        queue_st = repository.get_state("queueDetection", QueueDetectionState)
        loiter_st = repository.get_state("loitering", LoiteringState)
        occ_st = repository.get_state("zoneOccupancy", ZoneOccupancyState)

        snapshot = CameraAnalyticsSnapshot(
            camera_id=camera_id,
            pipeline_id=pipeline_id,
            timestamp_iso=now_iso,
            health=health_state,
            plugin_states=generic_plugin_states or {},
            people_counting=people_st,
            queue_detection=queue_st,
            loitering=loiter_st,
            zone_occupancy=occ_st,
        )

        return snapshot
