"""
Zone Occupancy Analytics Plugin Module.

Monitors human track count within spatial zones and emits StandardAnalyticsEvent objects.
"""

from __future__ import annotations

from typing import Any, Optional

from camera_analytics.entities.models import ZoneState
from camera_analytics.scene.models import Scene
from camera_analytics.sdk import (
    AnalyticsEvent,
    AnalyticsEventType,
    AnalyticsModule,
    AnalyticsResult,
)
from camera_analytics.sdk.events import EventSeverity, StandardAnalyticsEvent


class ZoneOccupancyModule(AnalyticsModule):
    """Zone Occupancy Analytics Module."""

    def __init__(self, name: str = "zone_occupancy") -> None:
        super().__init__(name=name, description="Zone Occupancy Monitoring Plugin")
        self.occupancy_threshold = 5
        self._last_occupancy: dict[str, int] = {}

    def update(self, context: Any) -> Optional[AnalyticsResult]:
        """Backward compatibility update hook."""
        return AnalyticsResult(module_name=self.name)

    def process_scene(self, scene: Scene) -> AnalyticsResult:
        """Process immutable Scene domain snapshot."""
        events: list[AnalyticsEvent] = []
        metrics: dict[str, Any] = {}

        # Count tracks inside each zone and collect track IDs
        zone_counts: dict[str, int] = {}
        zone_names: dict[str, str] = {}
        zone_active_tracks: dict[str, list[int]] = {}

        for z in scene.zones:
            zone_counts[z.zone_id] = 0
            zone_names[z.zone_id] = z.zone_name
            zone_active_tracks[z.zone_id] = []

        for track in scene.tracks:
            for z in scene.zones:
                if z.current_state in (ZoneState.ENTER, ZoneState.INSIDE):
                    zone_counts[z.zone_id] = zone_counts.get(z.zone_id, 0) + 1
                    if track.track_id not in zone_active_tracks[z.zone_id]:
                        zone_active_tracks[z.zone_id].append(track.track_id)

        # Emit events on change or threshold excess
        for zone_id, count in zone_counts.items():
            metrics[f"occupancy_{zone_id}"] = count
            last_cnt = self._last_occupancy.get(zone_id, -1)
            z_name = zone_names.get(zone_id, zone_id)

            if count != last_cnt:
                self._last_occupancy[zone_id] = count
                severity = EventSeverity.WARNING.value if count >= self.occupancy_threshold else EventSeverity.INFO.value
                msg = f"Zone '{z_name}' ({zone_id}) occupancy updated: {count} person(s)"

                std_event = StandardAnalyticsEvent(
                    event_type="ZONE_OCCUPANCY",
                    analytics_module=self.name,
                    source_module=self.name,
                    message=msg,
                    timestamp=str(scene.frame.timestamp),
                    camera_id=scene.camera.camera_id,
                    camera_name=scene.camera.camera_name,
                    zone_id=zone_id,
                    zone_name=z_name,
                    severity=severity,
                    payload={
                        "zone_id": zone_id,
                        "zone_name": z_name,
                        "occupancy_count": count,
                        "active_track_ids": zone_active_tracks.get(zone_id, []),
                        "threshold": self.occupancy_threshold,
                        "threshold_exceeded": count >= self.occupancy_threshold,
                    },
                    metadata={
                        "frame_index": scene.frame.frame_index,
                        "camera": scene.camera.to_dict(),
                        "frame": scene.frame.to_dict(),
                    },
                )

                # Legacy compatibility wrapper
                legacy_event = AnalyticsEvent(
                    event_id=std_event.event_id,
                    module_name=self.name,
                    event_type=AnalyticsEventType.COUNT_CHANGE,
                    message=msg,
                    timestamp=scene.frame.timestamp,
                    frame_index=scene.frame.frame_index,
                    zone_id=zone_id,
                    data=std_event.to_dict(),
                )
                events.append(legacy_event)

        return AnalyticsResult(
            module_name=self.name,
            events=events,
            metrics=metrics,
        )
