"""
Recording Service Plugin Implementation.

Wraps VideoSegmentRecorder and EventRecorder into an EventService plugin.
"""

from __future__ import annotations

import logging
from typing import Optional

from camera_analytics.communication.models import StandardAnalyticsEvent
from camera_analytics.eventing.models import PlatformEvent
from camera_analytics.recording import (
    EventRecorder,
    LocalStorageBackend,
    MetadataDatabase,
    PlaybackService,
    VideoSegmentRecorder,
)
from camera_analytics.services.context import ServiceContext
from camera_analytics.services.interfaces import EventService

logger = logging.getLogger(__name__)


class RecordingServicePlugin(EventService):
    """Recording Service Plugin executing segment recording and event reference indexing."""

    def __init__(self) -> None:
        super().__init__()
        self.storage: Optional[LocalStorageBackend] = None
        self.db: Optional[MetadataDatabase] = None
        self.recorder: Optional[VideoSegmentRecorder] = None
        self.evt_recorder: Optional[EventRecorder] = None
        self.playback: Optional[PlaybackService] = None

    def initialize(self, context: ServiceContext) -> None:
        super().initialize(context)
        storage_path = context.storage_dir
        self.storage = LocalStorageBackend(root_dir=storage_path)
        self.db = MetadataDatabase(db_path=storage_path / "metadata.db")

        self.recorder = VideoSegmentRecorder(
            camera_id=context.config.get("camera_id", "cam_default"),
            segment_duration_sec=context.config.get("segment_duration_sec", 60.0),
            storage_backend=self.storage,
            database=self.db,
        )
        self.evt_recorder = EventRecorder(recorder=self.recorder, database=self.db)
        self.playback = PlaybackService(database=self.db)
        logger.info("RecordingServicePlugin initialized")

    def start(self) -> None:
        if self.recorder:
            self.recorder.start()
        logger.info("RecordingServicePlugin started")

    def on_event(self, event: StandardAnalyticsEvent | PlatformEvent) -> None:
        if isinstance(event, StandardAnalyticsEvent):
            if self.evt_recorder:
                self.evt_recorder.record_event(event)

    def stop(self) -> None:
        if self.recorder:
            self.recorder.stop()
        logger.info("RecordingServicePlugin stopped")
