"""
Zone Exit Analytics Plugin Module.

Detects spatial zone exit transitions and emits StandardAnalyticsEvent objects.
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


class ZoneExitModule(AnalyticsModule):
    """Zone Exit Analytics Module."""

    def __init__(self, name: str = "zone_exit") -> None:
        super().__init__(name=name, description="Zone Exit Detection Plugin")
        self._previous_inside: dict[tuple[int, str], float] = {}

    def update(self, context: Any) -> Optional[AnalyticsResult]:
        """Backward compatibility update hook."""
        return AnalyticsResult(module_name=self.name)

    def process_scene(self, scene: Scene) -> AnalyticsResult:
        """Process immutable Scene domain snapshot."""
        events: list[AnalyticsEvent] = []
        current_inside: dict[tuple[int, str], float] = {}
        zone_names: dict[str, str] = {z.zone_id: z.zone_name for z in scene.zones}

        for track in scene.tracks:
            for zone in scene.zones:
                if zone.current_state in (ZoneState.ENTER, ZoneState.INSIDE):
                    key = (track.track_id, zone.zone_id)
                    entry_time = self._previous_inside.get(key, scene.frame.timestamp)
                    current_inside[key] = entry_time

        # Detect exits (keys present previously but missing now)
        exited_keys = set(self._previous_inside.keys()) - set(current_inside.keys())

        for track_id, zone_id in exited_keys:
            entry_ts = self._previous_inside[track_id, zone_id]
            dwell_duration = max(0.0, scene.frame.timestamp - entry_ts)
            z_name = zone_names.get(zone_id, zone_id)
            msg = f"Track #{track_id} exited zone '{z_name}' ({zone_id}) after {dwell_duration:.1f}s"

            std_event = StandardAnalyticsEvent(
                event_type="ZONE_EXIT",
                analytics_module=self.name,
                source_module=self.name,
                message=msg,
                timestamp=str(scene.frame.timestamp),
                camera_id=scene.camera.camera_id,
                camera_name=scene.camera.camera_name,
                track_id=track_id,
                zone_id=zone_id,
                zone_name=z_name,
                severity=EventSeverity.INFO.value,
                payload={
                    "track_id": track_id,
                    "zone_id": zone_id,
                    "zone_name": z_name,
                    "camera_id": scene.camera.camera_id,
                    "timestamp": scene.frame.timestamp,
                    "dwell_duration_seconds": round(dwell_duration, 2),
                },
                metadata={
                    "frame_index": scene.frame.frame_index,
                    "camera": scene.camera.to_dict(),
                    "frame": scene.frame.to_dict(),
                },
            )

            legacy_event = AnalyticsEvent(
                event_id=std_event.event_id,
                module_name=self.name,
                event_type=AnalyticsEventType.INFO,
                message=msg,
                timestamp=scene.frame.timestamp,
                frame_index=scene.frame.frame_index,
                track_id=track_id,
                zone_id=zone_id,
                data=std_event.to_dict(),
            )
            events.append(legacy_event)

        self._previous_inside = current_inside

        return AnalyticsResult(
            module_name=self.name,
            events=events,
            metrics={"active_zone_tracks": len(current_inside)},
        )
