"""
Loitering Detection Analytics Plugin Module.

Detects stationary loitering inside spatial zones and emits StandardAnalyticsEvent objects.
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


class LoiteringModule(AnalyticsModule):
    """Loitering Detection Analytics Module."""

    def __init__(self, name: str = "loitering") -> None:
        super().__init__(name=name, description="Loitering Detection Plugin")
        self.loitering_threshold_seconds = 15.0
        self.max_speed_threshold = 25.0
        self._loitering_start: dict[tuple[int, str], float] = {}
        self._alerted_tracks: set[tuple[int, str]] = set()

    def update(self, context: Any) -> Optional[AnalyticsResult]:
        """Backward compatibility update hook."""
        return AnalyticsResult(module_name=self.name)

    def process_scene(self, scene: Scene) -> AnalyticsResult:
        """Process immutable Scene domain snapshot."""
        events: list[AnalyticsEvent] = []
        active_keys: set[tuple[int, str]] = set()

        for track in scene.tracks:
            # Check speed for stationary condition
            is_slow = track.velocity.speed <= self.max_speed_threshold

            for zone in scene.zones:
                if zone.current_state in (ZoneState.ENTER, ZoneState.INSIDE) and is_slow:
                    key = (track.track_id, zone.zone_id)
                    active_keys.add(key)

                    if key not in self._loitering_start:
                        self._loitering_start[key] = scene.frame.timestamp

                    duration = scene.frame.timestamp - self._loitering_start[key]

                    if duration >= self.loitering_threshold_seconds and key not in self._alerted_tracks:
                        self._alerted_tracks.add(key)
                        msg = f"Loitering warning: Track #{track.track_id} stationary in zone '{zone.zone_name}' ({zone.zone_id}) for {duration:.1f}s"

                        std_event = StandardAnalyticsEvent(
                            event_type="LOITERING",
                            analytics_module=self.name,
                            source_module=self.name,
                            message=msg,
                            timestamp=str(scene.frame.timestamp),
                            camera_id=scene.camera.camera_id,
                            camera_name=scene.camera.camera_name,
                            track_id=track.track_id,
                            zone_id=zone.zone_id,
                            zone_name=zone.zone_name,
                            severity=EventSeverity.CRITICAL.value,
                            payload={
                                "track_id": track.track_id,
                                "zone_id": zone.zone_id,
                                "zone_name": zone.zone_name,
                                "camera_id": scene.camera.camera_id,
                                "timestamp": scene.frame.timestamp,
                                "loitering_duration_seconds": round(duration, 2),
                                "threshold_seconds": self.loitering_threshold_seconds,
                                "speed": round(track.velocity.speed, 2),
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
                            event_type=AnalyticsEventType.LOITERING_WARNING,
                            message=msg,
                            timestamp=scene.frame.timestamp,
                            frame_index=scene.frame.frame_index,
                            track_id=track.track_id,
                            zone_id=zone.zone_id,
                            data=std_event.to_dict(),
                        )
                        events.append(legacy_event)

        # Automatic garbage collection of state
        stale_keys = set(self._loitering_start.keys()) - active_keys
        for k in stale_keys:
            self._loitering_start.pop(k, None)
            self._alerted_tracks.discard(k)

        return AnalyticsResult(
            module_name=self.name,
            events=events,
            metrics={"loitering_tracks_monitored": len(self._loitering_start)},
        )
