"""
People analytics module.

Tracks person counts, zone occupancy, and emits events when
thresholds are exceeded. Demonstrates how to implement an
AnalyticsModule using the Sprint 2 FrameContext API.

Sprint 2 changes:
    - on_process() now receives FrameContext instead of (frame, tracks, frame_index).
    - Uses context.person_tracks (pre-computed cache) instead of manual filtering.
    - Implements get_output() returning PeopleModuleOutput for queryable state.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from camera_analytics.core.base_module import (
    AnalyticsModule,
    ModuleInfo,
    ModuleOutput,
)
from camera_analytics.core.config import ModuleConfig
from camera_analytics.models.event import EventCategory, EventSeverity

if TYPE_CHECKING:
    from camera_analytics.core.frame_context import FrameContext

logger = logging.getLogger(__name__)


@dataclass
class PeopleModuleOutput(ModuleOutput):
    """Queryable state for People Analytics.

    Exposes current analytics state that can be read by
    Rule Engine, Dashboard, or other consumers without
    relying on events.

    Attributes:
        current_count: Number of confirmed people in frame.
        zone_counts: People count per zone (keyed by zone_id).
        crowd_active: Whether crowd threshold is currently exceeded.
        crowd_threshold: The configured crowd threshold.
    """

    current_count: int = 0
    zone_counts: dict[str, int] = field(default_factory=dict)
    crowd_active: bool = False
    crowd_threshold: int = 0


class PeopleAnalytics(AnalyticsModule):
    """Analytics module for people detection, counting, and tracking.

    Monitors person tracks and emits events based on configurable
    thresholds. Uses FrameContext for all data access.

    Configuration keys (under 'modules.people_analytics')::

        confidence_threshold: float  # Min detection confidence (default: 0.5)
        crowd_threshold: int         # Person count to trigger crowd event (default: 10)

    Emitted event types::

        people.count_updated   — DEBUG   — Emitted each processed frame with current count.
        people.crowd_detected  — WARNING — Emitted when person count >= crowd_threshold.
        people.crowd_cleared   — INFO    — Emitted when crowd condition ends.
    """

    def __init__(self) -> None:
        super().__init__()
        self._confidence_threshold: float = 0.5
        self._crowd_threshold: int = 10
        self._current_count: int = 0
        self._zone_counts: dict[str, int] = {}
        self._crowd_active: bool = False
        self._last_frame_id: int = 0

    @property
    def module_info(self) -> ModuleInfo:
        """Module metadata."""
        return ModuleInfo(
            name="people_analytics",
            version="2.0.0",
            description="People counting, tracking, and crowd detection.",
            process_interval=1,
        )

    def on_initialize(self, config: ModuleConfig) -> None:
        """Load configuration for people analytics.

        Args:
            config: Module-specific configuration section.
        """
        self._confidence_threshold = config.get_float(
            "confidence_threshold", 0.5
        )
        self._crowd_threshold = config.get_int("crowd_threshold", 10)

        self._current_count = 0
        self._zone_counts = {}
        self._crowd_active = False

        self._logger.info(
            "People analytics initialized "
            "(confidence=%.2f, crowd_threshold=%d)",
            self._confidence_threshold,
            self._crowd_threshold,
        )

    def on_process(self, context: FrameContext) -> None:
        """Process a frame — count people and check crowd threshold.

        Uses FrameContext's pre-computed person_tracks cache for
        zero-cost filtering.

        Args:
            context: Immutable per-frame data snapshot.
        """
        # Use pre-computed person tracks from FrameContext
        # Additional confidence filter if needed
        person_tracks = [
            t
            for t in context.person_tracks
            if t.detection.confidence >= self._confidence_threshold
        ]

        self._current_count = len(person_tracks)
        self._last_frame_id = context.frame_id

        # Count people per zone
        self._zone_counts = {}
        for zone_id in context.zones:
            tracks_in_zone = context.get_tracks_in_zone(zone_id)
            zone_person_count = sum(
                1
                for t in tracks_in_zone
                if t.detection.is_person and t.is_confirmed
            )
            if zone_person_count > 0:
                self._zone_counts[zone_id] = zone_person_count

        # Emit count update
        self.emit_event(
            event_type="people.count_updated",
            category=EventCategory.COUNTING,
            severity=EventSeverity.DEBUG,
            frame_index=context.frame_id,
            message=f"People count: {self._current_count}",
            data={
                "count": self._current_count,
                "zone_counts": self._zone_counts,
            },
        )

        # Check crowd threshold
        self._check_crowd(context.frame_id)

    def on_shutdown(self) -> None:
        """Clean up people analytics resources."""
        self._logger.info(
            "People analytics shutdown (last count: %d)",
            self._current_count,
        )

    def get_output(self) -> PeopleModuleOutput:
        """Return current queryable state.

        Returns:
            PeopleModuleOutput with current counts and crowd status.
        """
        return PeopleModuleOutput(
            module_name=self.name,
            last_frame_id=self._last_frame_id,
            current_count=self._current_count,
            zone_counts=dict(self._zone_counts),
            crowd_active=self._crowd_active,
            crowd_threshold=self._crowd_threshold,
        )

    # --- Internal Logic ---

    def _check_crowd(self, frame_index: int) -> None:
        """Check if crowd threshold is exceeded and emit events.

        Emits crowd_detected when count rises above threshold,
        and crowd_cleared when it drops back below.

        Args:
            frame_index: Current frame index.
        """
        if self._current_count >= self._crowd_threshold:
            if not self._crowd_active:
                self._crowd_active = True
                self.emit_event(
                    event_type="people.crowd_detected",
                    category=EventCategory.COUNTING,
                    severity=EventSeverity.WARNING,
                    frame_index=frame_index,
                    message=(
                        f"Crowd detected: {self._current_count} people "
                        f"(threshold: {self._crowd_threshold})"
                    ),
                    data={
                        "count": self._current_count,
                        "threshold": self._crowd_threshold,
                    },
                )
        else:
            if self._crowd_active:
                self._crowd_active = False
                self.emit_event(
                    event_type="people.crowd_cleared",
                    category=EventCategory.COUNTING,
                    severity=EventSeverity.INFO,
                    frame_index=frame_index,
                    message=(
                        f"Crowd cleared: {self._current_count} people "
                        f"(threshold: {self._crowd_threshold})"
                    ),
                    data={
                        "count": self._current_count,
                        "threshold": self._crowd_threshold,
                    },
                )

    # --- Public Accessors ---

    @property
    def current_count(self) -> int:
        """Current number of detected people."""
        return self._current_count

    @property
    def is_crowd(self) -> bool:
        """Whether the crowd threshold is currently exceeded."""
        return self._crowd_active
