"""
Dwell Time Analytics Plugin Module.

Measures spatial zone dwell times per track and emits StandardAnalyticsEvent objects.
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


class DwellTimeModule(AnalyticsModule):
    """Dwell Time Analytics Module."""

    def __init__(self, name: str = "dwell_time") -> None:
        super().__init__(name=name, description="Dwell Time Analytics Plugin")
        self.dwell_threshold_seconds = 10.0
        self._dwell_start: dict[tuple[int, str], float] = {}
        self._alerted_tracks: set[tuple[int, str]] = set()

    def update(self, context: Any) -> Optional[AnalyticsResult]:
        """Backward compatibility update hook."""
        return AnalyticsResult(module_name=self.name)

    def process_scene(self, scene: Scene) -> AnalyticsResult:
        """Process immutable Scene domain snapshot."""
        events: list[AnalyticsEvent] = []
        active_keys: set[tuple[int, str]] = set()

        for track in scene.tracks:
            for zone in scene.zones:
                if zone.current_state in (ZoneState.ENTER, ZoneState.INSIDE):
                    key = (track.track_id, zone.zone_id)
                    active_keys.add(key)

                    if key not in self._dwell_start:
                        self._dwell_start[key] = scene.frame.timestamp

                    dwell_secs = scene.frame.timestamp - self._dwell_start[key]

                    if dwell_secs >= self.dwell_threshold_seconds and key not in self._alerted_tracks:
                        self._alerted_tracks.add(key)
                        msg = f"Track #{track.track_id} dwell time in zone '{zone.zone_name}' ({zone.zone_id}) exceeded threshold ({dwell_secs:.1f}s >= {self.dwell_threshold_seconds}s)"

                        std_event = StandardAnalyticsEvent(
                            event_type="DWELL_TIME",
                            analytics_module=self.name,
                            source_module=self.name,
                            message=msg,
                            timestamp=str(scene.frame.timestamp),
                            camera_id=scene.camera.camera_id,
                            camera_name=scene.camera.camera_name,
                            track_id=track.track_id,
                            zone_id=zone.zone_id,
                            zone_name=zone.zone_name,
                            severity=EventSeverity.WARNING.value,
                            payload={
                                "track_id": track.track_id,
                                "zone_id": zone.zone_id,
                                "zone_name": zone.zone_name,
                                "camera_id": scene.camera.camera_id,
                                "timestamp": scene.frame.timestamp,
                                "dwell_duration_seconds": round(dwell_secs, 2),
                                "threshold_seconds": self.dwell_threshold_seconds,
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
                            event_type=AnalyticsEventType.THRESHOLD_EXCEEDED,
                            message=msg,
                            timestamp=scene.frame.timestamp,
                            frame_index=scene.frame.frame_index,
                            track_id=track.track_id,
                            zone_id=zone.zone_id,
                            data=std_event.to_dict(),
                        )
                        events.append(legacy_event)

        # Automatic garbage collection of state
        stale_keys = set(self._dwell_start.keys()) - active_keys
        for k in stale_keys:
            self._dwell_start.pop(k, None)
            self._alerted_tracks.discard(k)

        return AnalyticsResult(
            module_name=self.name,
            events=events,
            metrics={"monitored_dwell_tracks": len(self._dwell_start)},
        )
