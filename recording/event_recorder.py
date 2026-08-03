"""
Event Recorder Subsystem Implementation.

Listens to `StandardAnalyticsEvent` objects from the platform and persists lightweight
references (segment ID, seek offset, track ID, zone ID, snapshot path) into `MetadataDatabase`.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

import numpy as np

from camera_analytics.communication.models import StandardAnalyticsEvent
from camera_analytics.recording.database import MetadataDatabase
from camera_analytics.recording.recorder import VideoSegmentRecorder
from camera_analytics.recording.schema import EventReference
from camera_analytics.recording.snapshot_generator import SnapshotGenerator

logger = logging.getLogger(__name__)


class EventRecorder:
    """Consumes StandardAnalyticsEvents and writes lightweight index references into MetadataDatabase."""

    def __init__(
        self,
        recorder: VideoSegmentRecorder,
        database: Optional[MetadataDatabase] = None,
        snapshot_generator: Optional[SnapshotGenerator] = None,
    ) -> None:
        self.recorder = recorder
        self.db = database or recorder.db
        self.snapshot_gen = snapshot_generator or SnapshotGenerator(database=self.db)

    def record_event(
        self,
        event: StandardAnalyticsEvent,
        frame: Optional[np.ndarray] = None,
        event_timestamp: Optional[float] = None,
    ) -> EventReference:
        """Record event reference into database and trigger snapshot generation if applicable.

        Args:
            event: StandardAnalyticsEvent instance.
            frame: Optional BGR frame image.
            event_timestamp: Epoch timestamp in seconds.

        Returns:
            Recorded EventReference instance.
        """
        ts = event_timestamp if event_timestamp is not None else time.time()
        segment_id = self.recorder.current_segment_id
        start_ts = self.recorder._segment_start_ts if self.recorder._segment_start_ts > 0 else ts
        seek_offset = max(0.0, ts - start_ts)

        # Generate snapshot if frame provided
        snap_meta = None
        if frame is not None:
            snap_meta = self.snapshot_gen.generate_snapshot(event, frame)

        snap_path = snap_meta.file_path if snap_meta else None

        evt_ref = EventReference(
            event_id=event.event_id,
            event_type=event.event_type,
            camera_id=event.camera_id,
            timestamp=ts,
            segment_id=segment_id,
            seek_offset_sec=seek_offset,
            frame_index=event.frame_index,
            track_id=event.track_id,
            zone_id=event.zone_id,
            severity=event.severity,
            snapshot_path=snap_path,
            message=event.message,
        )

        self.db.add_event_reference(evt_ref)
        logger.debug("EventRecorder recorded event reference '%s' (seek_offset=%.2fs)", event.event_id, seek_offset)
        return evt_ref
