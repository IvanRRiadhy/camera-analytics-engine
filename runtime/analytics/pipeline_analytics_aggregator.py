"""
Pipeline Analytics Aggregator Component (Sprint 4A).

Pipeline-scoped aggregator constructing enterprise GenericPluginState instances
with summary, byZone, and byCamera breakdowns for all registered plugins.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from camera_analytics.runtime.analytics.health_monitor import HealthMonitor
from camera_analytics.runtime.analytics.models import (
    CameraAnalytics,
    CameraAnalyticsSnapshot,
    GenericPluginState,
    LoiteringState,
    PeopleCountingState,
    QueueDetectionState,
    ZoneAnalytics,
    ZoneOccupancyState,
)
from camera_analytics.runtime.analytics.repository import PluginStateRepository

logger = logging.getLogger(__name__)


class PipelineAnalyticsAggregator:
    """Aggregates plugin state updates, zone breakdowns, and health metrics into enterprise contracts."""

    def __init__(self, camera_id: str, pipeline_id: str) -> None:
        self.camera_id = camera_id
        self.pipeline_id = pipeline_id
        self.repository = PluginStateRepository()
        self.health_monitor = HealthMonitor()

    def update_plugin_state(self, plugin_key: str, state_object: Any) -> None:
        """Update repository with typed plugin state."""
        self.repository.update_state(plugin_key, state_object)

    def update_zone_metric(self, plugin_key: str, zone_id: str, metrics: Dict[str, Any]) -> None:
        """Record zone-specific analytics metrics."""
        self.repository.update_zone_metric(plugin_key, zone_id, metrics, camera_id=self.camera_id)

    def build_generic_plugin_states(self) -> Dict[str, GenericPluginState]:
        """Construct enterprise summary, byZone, and byCamera states generically for all active plugins."""
        all_states = self.repository.get_all_states()
        generic_plugins: Dict[str, GenericPluginState] = {}

        for plugin_key, raw_state in all_states.items():
            if raw_state is None:
                continue

            summary_metrics: Dict[str, Any] = {}
            legacy_metrics: Dict[str, Any] = {}
            by_zone: Dict[str, ZoneAnalytics] = {}
            by_camera: Dict[str, CameraAnalytics] = {}

            # Handle known typed dataclasses generically
            if isinstance(raw_state, PeopleCountingState):
                summary_metrics = {
                    "current": raw_state.current,
                    "entered": raw_state.entered,
                    "exited": raw_state.exited,
                }
                legacy_metrics = {**summary_metrics}
            elif isinstance(raw_state, QueueDetectionState):
                summary_metrics = {
                    "queueLength": raw_state.queue_length,
                    "waitingPeople": raw_state.waiting_people,
                }
                legacy_metrics = {**summary_metrics}
            elif isinstance(raw_state, LoiteringState):
                summary_metrics = {
                    "active": raw_state.active_count,
                }
                legacy_metrics = {"active": raw_state.active_count, "trackIds": list(raw_state.track_ids)}
            elif isinstance(raw_state, ZoneOccupancyState):
                summary_metrics = {
                    "totalOccupancy": sum(raw_state.occupancy_by_zone.values()) if raw_state.occupancy_by_zone else 0
                }
                legacy_metrics = {"occupancyByZone": raw_state.occupancy_by_zone}
                for z_id, count in raw_state.occupancy_by_zone.items():
                    by_zone[z_id] = ZoneAnalytics(
                        zone_id=z_id,
                        zone_name=z_id.replace("_", " ").title(),
                        metrics={"occupancyCount": count},
                        reporting_cameras=[self.camera_id],
                    )
            elif isinstance(raw_state, dict):
                summary_metrics = {k: v for k, v in raw_state.items() if isinstance(v, (int, float, str, bool))}
                legacy_metrics = {**summary_metrics}
            else:
                # Generic object reflection
                for attr in dir(raw_state):
                    if not attr.startswith("_"):
                        val = getattr(raw_state, attr)
                        if isinstance(val, (int, float, str, bool)):
                            summary_metrics[attr] = val

            # Populate byZone entries from repository zone metrics
            zone_entries = self.repository.get_zone_metrics(plugin_key)
            for z_id, z_data in zone_entries.items():
                if z_id not in by_zone:
                    by_zone[z_id] = ZoneAnalytics(
                        zone_id=z_id,
                        zone_name=z_id.replace("_", " ").title(),
                        metrics=z_data.get("metrics", {}),
                        reporting_cameras=list(z_data.get("cameras", [self.camera_id])),
                    )

            # Populate byCamera entry
            by_camera[self.camera_id] = CameraAnalytics(
                camera_id=self.camera_id,
                camera_name=self.camera_id,
                metrics=summary_metrics,
            )

            generic_plugins[plugin_key] = GenericPluginState(
                plugin_code=plugin_key,
                summary=summary_metrics,
                by_zone=by_zone,
                by_camera=by_camera,
                legacy_metrics=legacy_metrics,
            )

        return generic_plugins

    def create_snapshot(
        self, worker: Optional[Any] = None, context: Optional[Any] = None
    ) -> CameraAnalyticsSnapshot:
        """Construct immutable CameraAnalyticsSnapshot using generic plugin states."""
        generic_plugin_states = self.build_generic_plugin_states()

        from camera_analytics.runtime.analytics.snapshot_builder import SnapshotBuilder
        return SnapshotBuilder.build_snapshot(
            camera_id=self.camera_id,
            pipeline_id=self.pipeline_id,
            repository=self.repository,
            health_monitor=self.health_monitor,
            generic_plugin_states=generic_plugin_states,
            worker=worker,
            context=context,
        )
