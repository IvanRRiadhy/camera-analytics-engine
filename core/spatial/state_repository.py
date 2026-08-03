"""
Track-Zone State Repository Component.

Manages persistent per-track spatial state records (OUTSIDE -> ENTER -> INSIDE -> EXIT -> OUTSIDE).
Does NOT generate domain events (SRP Compliance).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, Tuple

from camera_analytics.core.spatial.models import TrackSpatialState

logger = logging.getLogger(__name__)


class TrackZoneState(Enum):
    """Spatial relationship state of a Track relative to a Zone."""

    OUTSIDE = auto()
    ENTER = auto()
    INSIDE = auto()
    EXIT = auto()


@dataclass(slots=True)
class StateRecord:
    """Internal state machine record per (track_id, zone_id)."""

    track_id: int
    zone_id: str
    state: TrackZoneState = TrackZoneState.OUTSIDE
    entry_frame: int = 0
    entry_timestamp: float = 0.0
    dwell_frames: int = 0


class ZoneTrackerStateRepository:
    """State machine repository tracking spatial location states for tracks across frames."""

    def __init__(self) -> None:
        self._records: Dict[Tuple[int, str], StateRecord] = {}

    def get_record(self, track_id: int, zone_id: str) -> StateRecord:
        key = (track_id, zone_id)
        if key not in self._records:
            self._records[key] = StateRecord(track_id=track_id, zone_id=zone_id)
        return self._records[key]

    def update_state(
        self,
        track_id: int,
        zone_id: str,
        is_inside: bool,
        frame_index: int,
        timestamp: float,
    ) -> Tuple[TrackZoneState, TrackZoneState, int]:
        """Update track-zone state machine and return (prev_state, new_state, dwell_frames)."""
        record = self.get_record(track_id, zone_id)
        prev_state = record.state
        new_state = prev_state

        if is_inside:
            if prev_state in (TrackZoneState.OUTSIDE, TrackZoneState.EXIT):
                new_state = TrackZoneState.ENTER
                record.entry_frame = frame_index
                record.entry_timestamp = timestamp
                record.dwell_frames = 1
            elif prev_state in (TrackZoneState.ENTER, TrackZoneState.INSIDE):
                new_state = TrackZoneState.INSIDE
                record.dwell_frames += 1
        else:
            if prev_state in (TrackZoneState.ENTER, TrackZoneState.INSIDE):
                new_state = TrackZoneState.EXIT
            elif prev_state == TrackZoneState.EXIT:
                new_state = TrackZoneState.OUTSIDE
                record.dwell_frames = 0
            else:
                new_state = TrackZoneState.OUTSIDE
                record.dwell_frames = 0

        record.state = new_state
        return prev_state, new_state, record.dwell_frames

    def purge_stale_tracks(self, active_track_ids: set[int]) -> list[StateRecord]:
        """Remove state records for tracks that have exited the camera frame view."""
        stale_keys = [k for k in self._records if k[0] not in active_track_ids]
        stale_records: list[StateRecord] = []
        for k in stale_keys:
            rec = self._records.pop(k)
            if rec.state in (TrackZoneState.ENTER, TrackZoneState.INSIDE):
                stale_records.append(rec)
        return stale_records

    def clear(self) -> None:
        self._records.clear()
