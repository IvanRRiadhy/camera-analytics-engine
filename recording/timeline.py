"""
Timeline Builder Subsystem Implementation.

Constructs indexed chronological timeline entries for investigation workflows with multi-criteria filtering
(camera, event_type, severity, time range, track_id).
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from camera_analytics.recording.database import MetadataDatabase
from camera_analytics.recording.schema import TimelineEntry

logger = logging.getLogger(__name__)


class TimelineBuilder:
    """Chronological Timeline Builder for forensic analysis."""

    def __init__(self, database: MetadataDatabase) -> None:
        self.db = database

    def build_timeline(
        self,
        camera_id: Optional[str] = None,
        event_type: Optional[str] = None,
        severity: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        track_id: Optional[int] = None,
        limit: int = 100,
    ) -> list[TimelineEntry]:
        """Build a sorted chronological timeline of event entries matching criteria."""
        event_refs = self.db.query_events(
            camera_id=camera_id,
            event_type=event_type,
            severity=severity,
            start_time=start_time,
            end_time=end_time,
            track_id=track_id,
            limit=limit,
        )

        entries: list[TimelineEntry] = []
        for ref in event_refs:
            entries.append(
                TimelineEntry(
                    entry_id=f"tl_{ref.event_id[:8]}",
                    timestamp=ref.timestamp,
                    event_type=ref.event_type,
                    severity=ref.severity,
                    camera_id=ref.camera_id,
                    segment_id=ref.segment_id,
                    seek_offset_sec=ref.seek_offset_sec,
                    track_id=ref.track_id,
                    zone_id=ref.zone_id,
                    snapshot_path=ref.snapshot_path,
                    message=ref.message,
                )
            )

        entries.sort(key=lambda x: x.timestamp)
        return entries
