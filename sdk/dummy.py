"""
Dummy Analytics Plugin for SDK Validation.

Sample implementation of `AnalyticsModule` used to validate the Analytics SDK lifecycle,
event callback delivery, exception handling, and result collection.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from camera_analytics.sdk.models import (
    AnalyticsContext,
    AnalyticsEvent,
    AnalyticsEventType,
    AnalyticsResult,
)
from camera_analytics.sdk.module import AnalyticsModule
from camera_analytics.sdk.registry import AnalyticsRegistry

if TYPE_CHECKING:
    from camera_analytics.core.zone_engine import ZoneEvent
    from camera_analytics.models.track import Track

logger = logging.getLogger(__name__)


@AnalyticsRegistry.register("dummy_analytics")
class DummyAnalytics(AnalyticsModule):
    """Dummy Analytics plugin used exclusively for SDK verification and lifecycle testing.

    Tracks active track counts, counts zone events, and emits structured AnalyticsEvent objects.
    """

    def __init__(self, name: str = "dummy_analytics", description: str = "SDK Validation Dummy Analytics") -> None:
        super().__init__(name=name, description=description)
        self.created_tracks_count = 0
        self.confirmed_tracks_count = 0
        self.lost_tracks_count = 0
        self.removed_tracks_count = 0
        self.enter_zone_events_count = 0
        self.exit_zone_events_count = 0
        self.stay_zone_events_count = 0
        self._pending_events: list[AnalyticsEvent] = []

    def on_initialize(self, context: AnalyticsContext) -> None:
        """Initialize dummy analytics counters."""
        logger.info("DummyAnalytics: Initialized with config: %s", context.config)

    def on_start(self) -> None:
        """Start dummy analytics plugin."""
        logger.info("DummyAnalytics: Started")

    def on_track_created(self, track: Track) -> None:
        """Track creation callback."""
        self.created_tracks_count += 1
        logger.debug("DummyAnalytics: Track #%d created", track.track_id)

    def on_track_confirmed(self, track: Track) -> None:
        """Track confirmation callback."""
        self.confirmed_tracks_count += 1
        logger.debug("DummyAnalytics: Track #%d confirmed", track.track_id)

    def on_track_lost(self, track: Track) -> None:
        """Track lost callback."""
        self.lost_tracks_count += 1
        logger.debug("DummyAnalytics: Track #%d lost", track.track_id)

    def on_track_removed(self, track: Track) -> None:
        """Track removed callback."""
        self.removed_tracks_count += 1
        logger.debug("DummyAnalytics: Track #%d removed", track.track_id)

    def on_zone_enter(self, event: ZoneEvent) -> None:
        """Zone entry spatial callback."""
        self.enter_zone_events_count += 1
        analytics_evt = AnalyticsEvent(
            event_id=f"evt_enter_{event.track_id}_{event.zone_id}_{event.frame_index}",
            module_name=self.name,
            event_type=AnalyticsEventType.ZONE_INTRUSION,
            message=f"Track #{event.track_id} entered zone '{event.zone_name}'",
            timestamp=event.timestamp,
            frame_index=event.frame_index,
            track_id=event.track_id,
            zone_id=event.zone_id,
            data={"ground_point": event.ground_point},
        )
        self._pending_events.append(analytics_evt)
        logger.info("DummyAnalytics: %s", analytics_evt.message)

    def on_zone_exit(self, event: ZoneEvent) -> None:
        """Zone exit spatial callback."""
        self.exit_zone_events_count += 1
        analytics_evt = AnalyticsEvent(
            event_id=f"evt_exit_{event.track_id}_{event.zone_id}_{event.frame_index}",
            module_name=self.name,
            event_type=AnalyticsEventType.INFO,
            message=f"Track #{event.track_id} exited zone '{event.zone_name}' (stayed {event.dwell_frames} frames)",
            timestamp=event.timestamp,
            frame_index=event.frame_index,
            track_id=event.track_id,
            zone_id=event.zone_id,
            data={"dwell_frames": event.dwell_frames},
        )
        self._pending_events.append(analytics_evt)
        logger.info("DummyAnalytics: %s", analytics_evt.message)

    def on_zone_stay(self, event: ZoneEvent) -> None:
        """Zone stay spatial callback."""
        self.stay_zone_events_count += 1

    def update(self, context: AnalyticsContext) -> AnalyticsResult:
        """Process frame context and generate AnalyticsResult."""
        active_count = len(context.active_tracks)

        events_to_emit = list(self._pending_events)
        self._pending_events.clear()

        metrics = {
            "active_tracks": active_count,
            "created_tracks_total": self.created_tracks_count,
            "confirmed_tracks_total": self.confirmed_tracks_count,
            "enter_zone_events_total": self.enter_zone_events_count,
            "exit_zone_events_total": self.exit_zone_events_count,
        }

        statistics = {
            "stay_zone_events_total": self.stay_zone_events_count,
            "lost_tracks_total": self.lost_tracks_count,
            "removed_tracks_total": self.removed_tracks_count,
        }

        return AnalyticsResult(
            module_name=self.name,
            events=events_to_emit,
            metrics=metrics,
            statistics=statistics,
        )

    def on_stop(self) -> None:
        """Stop dummy analytics plugin."""
        logger.info("DummyAnalytics: Stopped")

    def on_dispose(self) -> None:
        """Dispose dummy analytics plugin."""
        logger.info("DummyAnalytics: Disposed")
