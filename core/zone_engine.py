"""
Standalone Zone Engine core implementation.

Provides spatial geometric relationship tracking using ZoneTrackerStateRepository
and TransitionDetector. Emits enriched FrameSpatialSnapshot payloads.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional, Sequence

from camera_analytics.core.spatial.models import (
    FrameSpatialSnapshot,
    GroundPointSource,
    PixelPoint,
    TrackSpatialState,
    ZoneTransitionEvent,
)
from camera_analytics.core.spatial.state_repository import (
    TrackZoneState,
    ZoneTrackerStateRepository,
)
from camera_analytics.core.spatial.transition_detector import TransitionDetector
from camera_analytics.core.spatial.zone_manager import ZoneManager

logger = logging.getLogger(__name__)


class ZoneEngine:
    """Core state-machine tracking engine utilizing ZoneTrackerStateRepository and TransitionDetector."""

    def __init__(self, zone_manager: ZoneManager | None = None) -> None:
        self._zone_manager = zone_manager
        self._state_repo = ZoneTrackerStateRepository()

    def set_zone_manager(self, zone_manager: ZoneManager) -> None:
        self._zone_manager = zone_manager

    def process_context(
        self,
        tracks: list[dict[str, Any]],
        pose_keypoints: list[Any],
        frame_index: int,
        timestamp: float,
        camera_id: str,
    ) -> FrameSpatialSnapshot:
        """Process spatial relationships for tracks in SharedAnalyticsContext and build FrameSpatialSnapshot."""
        from camera_analytics.context.services import GroundPointEstimator

        active_zones = self._zone_manager.get_zones(camera_id) if self._zone_manager else []
        occupancy_counts: dict[str, int] = {z.id: 0 for z in active_zones}
        events: list[ZoneTransitionEvent] = []
        track_states: dict[int, TrackSpatialState] = {}
        current_track_ids: set[int] = set()

        for trk_idx, trk in enumerate(tracks):
            tid = int(trk.get("track_id", trk_idx + 1))
            current_track_ids.add(tid)
            bbox = trk.get("bbox", [0.0, 0.0, 100.0, 100.0])

            # Extract pose keypoints for this track if present
            kps = pose_keypoints[trk_idx] if trk_idx < len(pose_keypoints) else None
            ground_pt, pt_source = GroundPointEstimator.estimate(bbox, kps)

            sp_state = TrackSpatialState(
                track_id=tid,
                ground_point=ground_pt,
                ground_point_source=pt_source,
            )

            # Query matching zones via ISpatialIndex accelerated ZoneManager
            matching_zones = self._zone_manager.find_matching_zones(camera_id, ground_pt) if self._zone_manager else []
            matching_zone_ids = {z.id for z in matching_zones}

            for zone in active_zones:
                is_inside = zone.id in matching_zone_ids
                prev_st, new_st, dwell_frames = self._state_repo.update_state(
                    track_id=tid,
                    zone_id=zone.id,
                    is_inside=is_inside,
                    frame_index=frame_index,
                    timestamp=timestamp,
                )

                if new_st in (TrackZoneState.ENTER, TrackZoneState.INSIDE):
                    sp_state.active_zone_ids.add(zone.id)
                    sp_state.zone_dwell_frames[zone.id] = dwell_frames
                    occupancy_counts[zone.id] += 1

                # Transition Detection
                rec = self._state_repo.get_record(tid, zone.id)
                dwell_sec = timestamp - rec.entry_timestamp if rec.entry_timestamp > 0 else 0.0

                evt = TransitionDetector.detect_transition(
                    prev_state=prev_st,
                    new_state=new_st,
                    track_id=tid,
                    zone=zone,
                    ground_point=ground_pt,
                    ground_point_source=pt_source,
                    frame_index=frame_index,
                    timestamp=timestamp,
                    dwell_frames=dwell_frames,
                    dwell_seconds=dwell_sec,
                    camera_id=camera_id,
                )
                if evt is not None:
                    events.append(evt)

            track_states[tid] = sp_state

        # Purge stale tracks that exited the video view
        stale_records = self._state_repo.purge_stale_tracks(current_track_ids)
        for s_rec in stale_records:
            z_obj = self._zone_manager.get_zone_by_id(camera_id, s_rec.zone_id) if self._zone_manager else None
            if z_obj:
                evt = TransitionDetector.detect_transition(
                    prev_state=TrackZoneState.INSIDE,
                    new_state=TrackZoneState.EXIT,
                    track_id=s_rec.track_id,
                    zone=z_obj,
                    ground_point=PixelPoint(0, 0),
                    ground_point_source=GroundPointSource.BBOX_BOTTOM_CENTER,
                    frame_index=frame_index,
                    timestamp=timestamp,
                    dwell_frames=s_rec.dwell_frames,
                    dwell_seconds=timestamp - s_rec.entry_timestamp,
                    camera_id=camera_id,
                )
                if evt is not None:
                    events.append(evt)

        return FrameSpatialSnapshot(
            frame_index=frame_index,
            timestamp=timestamp,
            camera_id=camera_id,
            active_zones=active_zones,
            track_states=track_states,
            events=events,
            occupancy_counts=occupancy_counts,
        )

    def clear(self) -> None:
        self._state_repo.clear()
