"""
Transition Detector Component.

Detects state diffs and constructs rich ZoneTransitionEvent domain objects (SRP Compliance).
"""

from __future__ import annotations

import logging
from typing import Optional

from camera_analytics.core.spatial.models import (
    GroundPointSource,
    PixelPoint,
    ZoneEventType,
    ZoneModel,
    ZoneTransitionEvent,
)
from camera_analytics.core.spatial.state_repository import TrackZoneState

logger = logging.getLogger(__name__)


class TransitionDetector:
    """Transition Detector constructing enriched ZoneTransitionEvent payloads."""

    @staticmethod
    def detect_transition(
        prev_state: TrackZoneState,
        new_state: TrackZoneState,
        track_id: int,
        zone: ZoneModel,
        ground_point: PixelPoint,
        ground_point_source: GroundPointSource,
        frame_index: int,
        timestamp: float,
        dwell_frames: int,
        dwell_seconds: float,
        camera_id: str,
    ) -> Optional[ZoneTransitionEvent]:
        event_type: Optional[ZoneEventType] = None

        if new_state == TrackZoneState.ENTER:
            event_type = ZoneEventType.ENTER
        elif new_state == TrackZoneState.INSIDE and prev_state in (TrackZoneState.ENTER, TrackZoneState.INSIDE):
            event_type = ZoneEventType.STAY
        elif new_state == TrackZoneState.EXIT:
            event_type = ZoneEventType.EXIT

        if event_type is None:
            return None

        event = ZoneTransitionEvent(
            event_type=event_type,
            track_id=track_id,
            zone_id=zone.id,
            zone_name=zone.name,
            ground_point=ground_point.to_tuple(),
            ground_point_source=ground_point_source,
            frame_index=frame_index,
            timestamp=timestamp,
            dwell_frames=dwell_frames,
            dwell_duration_seconds=dwell_seconds,
            camera_id=camera_id,
        )

        logger.debug(
            "[Spatial Event] Track %d %s Zone '%s' (Dwell: %d frames / %.1fs)",
            track_id,
            event_type.name,
            zone.name,
            dwell_frames,
            dwell_seconds,
        )
        return event
