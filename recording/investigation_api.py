"""
Incident Investigation API Layer.

High-level forensic investigation API for querying incidents, events, tracks, video segments,
and evidence packages.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from camera_analytics.recording.database import MetadataDatabase
from camera_analytics.recording.playback import PlaybackService
from camera_analytics.recording.schema import EventReference, PlaybackSeekResult, TimelineEntry
from camera_analytics.recording.timeline import TimelineBuilder

logger = logging.getLogger(__name__)


class InvestigationAPI:
    """Forensic Incident Investigation API Service."""

    def __init__(self, database: MetadataDatabase, playback_service: Optional[PlaybackService] = None) -> None:
        self.db = database
        self.playback = playback_service or PlaybackService(database)
        self.timeline_builder = TimelineBuilder(database)

    def query_events_between(
        self,
        start_time: float,
        end_time: float,
        camera_id: Optional[str] = None,
        event_type: Optional[str] = None,
        severity: Optional[str] = None,
    ) -> list[EventReference]:
        """Query all events occurring between two timestamps."""
        return self.db.query_events(
            camera_id=camera_id,
            event_type=event_type,
            severity=severity,
            start_time=start_time,
            end_time=end_time,
        )

    def query_track_history(self, track_id: int, camera_id: Optional[str] = None) -> list[EventReference]:
        """Find all analytics events associated with a specific Track ID."""
        return self.db.query_events(track_id=track_id, camera_id=camera_id)

    def get_evidence_package(self, event_id: str) -> dict[str, Any]:
        """Gather full evidence package around an Event ID (segment, seek offset, snapshot, timeline)."""
        events = self.db.query_events(limit=1000)
        matched_evt = next((e for e in events if e.event_id == event_id), None)

        if not matched_evt:
            return {"error": f"Event '{event_id}' not found."}

        playback_info = self.playback.seek_timestamp(matched_evt.camera_id, matched_evt.timestamp)

        return {
            "event": matched_evt.to_dict(),
            "playback_seek": playback_info.to_dict() if playback_info else None,
            "snapshot_path": matched_evt.snapshot_path,
        }

    def generate_timeline(
        self,
        camera_id: Optional[str] = None,
        event_type: Optional[str] = None,
        severity: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
    ) -> list[dict[str, Any]]:
        """Generate formatted investigation timeline entries."""
        entries = self.timeline_builder.build_timeline(
            camera_id=camera_id,
            event_type=event_type,
            severity=severity,
            start_time=start_time,
            end_time=end_time,
        )
        return [e.to_dict() for e in entries]
