"""
Reference Analytics Module Template.

Official starter code template for building new Analytics Modules on the platform.
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


class ReferenceAnalyticsModule(AnalyticsModule):
    """Official reference implementation template for AnalyticsModule."""

    def __init__(self, name: str = "reference_analytics_plugin") -> None:
        super().__init__(name=name, description="Reference Analytics Plugin Template")
        self.processed_frames = 0

    def update(self, context: Any) -> Optional[AnalyticsResult]:
        """Backward compatibility update hook."""
        return AnalyticsResult(module_name=self.name)

    def process_scene(self, scene: Scene) -> AnalyticsResult:
        """Process immutable Scene domain snapshot.

        Args:
            scene: Immutable Scene domain snapshot.

        Returns:
            AnalyticsResult instance containing events and metrics.
        """
        self.processed_frames += 1
        events: list[AnalyticsEvent] = []

        # Example: Emit an AnalyticsEvent every 100 frames
        if scene.frame.frame_index % 100 == 0:
            events.append(
                AnalyticsEvent(
                    event_id=f"evt_ref_{scene.frame.frame_index}",
                    module_name=self.name,
                    event_type=AnalyticsEventType.INFO,
                    message=f"[{self.name}] Processed frame {scene.frame.frame_index} with {len(scene.tracks)} active tracks",
                    timestamp=scene.frame.timestamp,
                    frame_index=scene.frame.frame_index,
                )
            )

        return AnalyticsResult(
            module_name=self.name,
            events=events,
            metrics={
                "processed_frames": self.processed_frames,
                "active_tracks_count": len(scene.tracks),
            },
        )
