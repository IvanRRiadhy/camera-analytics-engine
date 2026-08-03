"""
Crowd Detection Analytics Plugin Module.

Evaluates frame and spatial track density, emitting StandardAnalyticsEvent objects when crowd thresholds are met.
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


class CrowdDetectionModule(AnalyticsModule):
    """Crowd Detection Analytics Module."""

    def __init__(self, name: str = "crowd_detection") -> None:
        super().__init__(name=name, description="Crowd Density Detection Plugin")
        self.crowd_threshold = 4
        self._is_crowd_active = False

    def update(self, context: Any) -> Optional[AnalyticsResult]:
        """Backward compatibility update hook."""
        return AnalyticsResult(module_name=self.name)

    def process_scene(self, scene: Scene) -> AnalyticsResult:
        """Process immutable Scene domain snapshot."""
        events: list[AnalyticsEvent] = []
        track_count = len(scene.tracks)
        active_track_ids = [t.track_id for t in scene.tracks]
        is_crowd = track_count >= self.crowd_threshold

        # Trigger event on crowd state transition
        if is_crowd and not self._is_crowd_active:
            self._is_crowd_active = True
            msg = f"Crowd alert: {track_count} individuals detected (Threshold >= {self.crowd_threshold})"

            std_event = StandardAnalyticsEvent(
                event_type="CROWD_ALERT",
                analytics_module=self.name,
                source_module=self.name,
                message=msg,
                timestamp=str(scene.frame.timestamp),
                camera_id=scene.camera.camera_id,
                camera_name=scene.camera.camera_name,
                severity=EventSeverity.CRITICAL.value,
                payload={
                    "total_tracks": track_count,
                    "active_track_ids": active_track_ids,
                    "crowd_threshold": self.crowd_threshold,
                    "camera_id": scene.camera.camera_id,
                    "timestamp": scene.frame.timestamp,
                    "density_per_kpx": round(track_count / max(1.0, (scene.frame.frame_width * scene.frame.frame_height / 1000.0)), 4),
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
                event_type=AnalyticsEventType.CROWD_DETECTED,
                message=msg,
                timestamp=scene.frame.timestamp,
                frame_index=scene.frame.frame_index,
                data=std_event.to_dict(),
            )
            events.append(legacy_event)

        elif not is_crowd and self._is_crowd_active:
            self._is_crowd_active = False

        return AnalyticsResult(
            module_name=self.name,
            events=events,
            metrics={
                "track_count": track_count,
                "is_crowd_active": self._is_crowd_active,
                "threshold": self.crowd_threshold,
            },
        )
