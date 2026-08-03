"""
Zone Enter Analytics Plugin Module.

Detects spatial zone entry transitions and emits StandardAnalyticsEvent objects.
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


class ZoneEnterModule(AnalyticsModule):
    """Zone Enter Analytics Module."""

    def __init__(self, name: str = "zone_enter") -> None:
        super().__init__(name=name, description="Zone Entry Detection Plugin")
        self._inside_tracks: set[tuple[int, str]] = set()

    def update(self, context: Any) -> Optional[AnalyticsResult]:
        """Backward compatibility update hook."""
        return AnalyticsResult(module_name=self.name)

    def process_scene(self, scene: Scene) -> AnalyticsResult:
        """Process immutable Scene domain snapshot."""
        events: list[AnalyticsEvent] = []
        current_inside: set[tuple[int, str]] = set()

        for track in scene.tracks:
            for zone in scene.zones:
                if zone.current_state in (ZoneState.ENTER, ZoneState.INSIDE):
                    key = (track.track_id, zone.zone_id)
                    current_inside.add(key)

                    # Trigger ZONE_ENTER event on transition
                    if key not in self._inside_tracks:
                        msg = f"Track #{track.track_id} entered zone '{zone.zone_name}' ({zone.zone_id})"
                        std_event = StandardAnalyticsEvent(
                            event_type="ZONE_ENTER",
                            analytics_module=self.name,
                            source_module=self.name,
                            message=msg,
                            timestamp=str(scene.frame.timestamp),
                            camera_id=scene.camera.camera_id,
                            camera_name=scene.camera.camera_name,
                            track_id=track.track_id,
                            zone_id=zone.zone_id,
                            zone_name=zone.zone_name,
                            severity=EventSeverity.INFO.value,
                            payload={
                                "track_id": track.track_id,
                                "zone_id": zone.zone_id,
                                "zone_name": zone.zone_name,
                                "camera_id": scene.camera.camera_id,
                                "timestamp": scene.frame.timestamp,
                                "track_age": track.track_age,
                                "ground_point": track.ground_point.to_dict() if track.ground_point else None,
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
                            event_type=AnalyticsEventType.ZONE_INTRUSION,
                            message=msg,
                            timestamp=scene.frame.timestamp,
                            frame_index=scene.frame.frame_index,
                            track_id=track.track_id,
                            zone_id=zone.zone_id,
                            data=std_event.to_dict(),
                        )
                        events.append(legacy_event)

        # Automatic garbage collection of state
        self._inside_tracks = current_inside

        return AnalyticsResult(
            module_name=self.name,
            events=events,
            metrics={"inside_tracks_count": len(self._inside_tracks)},
        )
