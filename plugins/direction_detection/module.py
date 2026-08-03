"""
Direction Detection Analytics Plugin Module.

Evaluates track movement direction and heading, emitting StandardAnalyticsEvent objects on directional violations.
"""

from __future__ import annotations

from typing import Any, Optional

from camera_analytics.scene.models import Scene
from camera_analytics.sdk import (
    AnalyticsEvent,
    AnalyticsEventType,
    AnalyticsModule,
    AnalyticsResult,
)
from camera_analytics.sdk.events import EventSeverity, StandardAnalyticsEvent


class DirectionDetectionModule(AnalyticsModule):
    """Direction Detection Analytics Module."""

    def __init__(self, name: str = "direction_detection") -> None:
        super().__init__(name=name, description="Direction Violation Detection Plugin")
        self.restricted_cardinals = {"S", "SW", "SE"}
        self.min_speed_threshold = 10.0
        self._alerted_tracks: set[int] = set()

    def update(self, context: Any) -> Optional[AnalyticsResult]:
        """Backward compatibility update hook."""
        return AnalyticsResult(module_name=self.name)

    def process_scene(self, scene: Scene) -> AnalyticsResult:
        """Process immutable Scene domain snapshot."""
        events: list[AnalyticsEvent] = []
        active_ids = {t.track_id for t in scene.tracks}

        for track in scene.tracks:
            cardinal = track.direction.cardinal_direction
            speed = track.velocity.speed

            if speed >= self.min_speed_threshold and cardinal in self.restricted_cardinals:
                if track.track_id not in self._alerted_tracks:
                    self._alerted_tracks.add(track.track_id)
                    msg = f"Wrong direction violation: Track #{track.track_id} moving heading '{cardinal}' ({track.direction.heading_degrees:.1f}°)"

                    std_event = StandardAnalyticsEvent(
                        event_type="DIRECTION_VIOLATION",
                        analytics_module=self.name,
                        source_module=self.name,
                        message=msg,
                        timestamp=str(scene.frame.timestamp),
                        camera_id=scene.camera.camera_id,
                        camera_name=scene.camera.camera_name,
                        track_id=track.track_id,
                        severity=EventSeverity.WARNING.value,
                        payload={
                            "track_id": track.track_id,
                            "camera_id": scene.camera.camera_id,
                            "timestamp": scene.frame.timestamp,
                            "heading_degrees": track.direction.heading_degrees,
                            "cardinal_direction": cardinal,
                            "restricted_cardinals": list(self.restricted_cardinals),
                            "speed": round(speed, 2),
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
                        event_type=AnalyticsEventType.LINE_CROSSED,
                        message=msg,
                        timestamp=scene.frame.timestamp,
                        frame_index=scene.frame.frame_index,
                        track_id=track.track_id,
                        data=std_event.to_dict(),
                    )
                    events.append(legacy_event)

        # Automatic garbage collection of state
        self._alerted_tracks.intersection_update(active_ids)

        return AnalyticsResult(
            module_name=self.name,
            events=events,
            metrics={"alerted_tracks_count": len(self._alerted_tracks)},
        )
