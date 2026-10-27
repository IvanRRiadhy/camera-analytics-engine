"""
Human Snapshot Mapper (Sprint H1.5A).

Isolates internal domain HumanState & HumanRepresentation models from public network payload schemas.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from camera_analytics.core.human.models import HumanRepresentation, HumanState

logger = logging.getLogger(__name__)


class HumanSnapshotMapper:
    """Maps internal HumanState and HumanRepresentation objects to future-proof public JSON dictionary schemas."""

    @staticmethod
    def map_track_telemetry(
        representation: Optional[HumanRepresentation],
        state: Optional[HumanState],
    ) -> dict[str, Any]:
        """Map a single track's internal domain state to public network JSON payload dictionary."""
        track_id = representation.track_id if representation else (state.track_id if state else 0)
        
        # Demographics fields (age & gender remain NULL until Sprint H1.5B)
        gender = state.demographics.gender if state else None
        gender_conf = state.demographics.gender_confidence if state else 0.0
        gender_lock = state.demographics.gender_lock if state else "UNLOCKED"

        age = state.demographics.age if state else None
        age_conf = state.demographics.age_confidence if state else 0.0
        age_lock = state.demographics.age_lock if state else "UNLOCKED"

        # Quality & Visibility
        face_quality = representation.face_quality_score if representation else 0.0
        visibility = representation.visibility_score if representation else 1.0

        # Processing state
        proc_state = "COMPLETED" if (gender_lock == "LOCKED" and age_lock == "LOCKED") else "IDLE"

        return {
            "trackId": track_id,
            "gender": gender,
            "genderConfidence": round(gender_conf, 3),
            "genderLock": gender_lock,
            "age": age,
            "ageConfidence": round(age_conf, 3),
            "ageLock": age_lock,
            "faceQuality": round(face_quality, 3),
            "visibility": round(visibility, 3),
            "processingState": proc_state,
        }

    @staticmethod
    def map_snapshot_payload(
        summary: dict[str, Any],
        representations: dict[int, HumanRepresentation],
        states: dict[int, HumanState],
    ) -> dict[str, Any]:
        """Map full human domain frame state to top-level public "human" JSON payload."""
        tracks_payload: dict[str, Any] = {}

        all_track_ids = set(representations.keys()) | set(states.keys())
        for t_id in all_track_ids:
            rep = representations.get(t_id)
            st = states.get(t_id)
            tracks_payload[str(t_id)] = HumanSnapshotMapper.map_track_telemetry(rep, st)

        return {
            "summary": summary,
            "tracks": tracks_payload,
        }
