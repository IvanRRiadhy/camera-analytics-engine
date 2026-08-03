"""
Queue Detection Analytics Plugin Module.

Evaluates queue line formation and queue wait times, emitting StandardAnalyticsEvent objects.
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


class QueueDetectionModule(AnalyticsModule):
    """Queue Detection Analytics Module."""

    def __init__(self, name: str = "queue_detection") -> None:
        super().__init__(name=name, description="Queue Monitoring Plugin")
        self.max_queue_length = 3
        self.max_queue_speed = 30.0
        self._queue_state: dict[str, set[int]] = {}
        self._alerted_zones: set[str] = set()

    def update(self, context: Any) -> Optional[AnalyticsResult]:
        """Backward compatibility update hook."""
        return AnalyticsResult(module_name=self.name)

    def process_scene(self, scene: Scene) -> AnalyticsResult:
        """Process immutable Scene domain snapshot."""
        events: list[AnalyticsEvent] = []
        current_zone_queues: dict[str, set[int]] = {z.zone_id: set() for z in scene.zones}
        zone_names: dict[str, str] = {z.zone_id: z.zone_name for z in scene.zones}

        for track in scene.tracks:
            is_waiting = track.velocity.speed <= self.max_queue_speed
            for zone in scene.zones:
                if zone.current_state in (ZoneState.ENTER, ZoneState.INSIDE) and is_waiting:
                    current_zone_queues[zone.zone_id].add(track.track_id)

        for zone_id, queue_tracks in current_zone_queues.items():
            queue_len = len(queue_tracks)
            z_name = zone_names.get(zone_id, zone_id)

            if queue_len >= self.max_queue_length and zone_id not in self._alerted_zones:
                self._alerted_zones.add(zone_id)
                msg = f"Queue alert: Zone '{z_name}' ({zone_id}) queue length {queue_len} exceeds limit (>= {self.max_queue_length})"

                std_event = StandardAnalyticsEvent(
                    event_type="QUEUE_ALERT",
                    analytics_module=self.name,
                    source_module=self.name,
                    message=msg,
                    timestamp=str(scene.frame.timestamp),
                    camera_id=scene.camera.camera_id,
                    camera_name=scene.camera.camera_name,
                    zone_id=zone_id,
                    zone_name=z_name,
                    severity=EventSeverity.WARNING.value,
                    payload={
                        "zone_id": zone_id,
                        "zone_name": z_name,
                        "camera_id": scene.camera.camera_id,
                        "timestamp": scene.frame.timestamp,
                        "queue_length": queue_len,
                        "max_queue_length": self.max_queue_length,
                        "track_ids": list(queue_tracks),
                        "estimated_wait_time_seconds": round(queue_len * 15.0, 1),
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
                    zone_id=zone_id,
                    data=std_event.to_dict(),
                )
                events.append(legacy_event)

            elif queue_len < self.max_queue_length:
                self._alerted_zones.discard(zone_id)

        self._queue_state = current_zone_queues

        return AnalyticsResult(
            module_name=self.name,
            events=events,
            metrics={"monitored_queues": len(self._queue_state)},
        )
