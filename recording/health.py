"""
Recording Subsystem Health & Observability Subsystem.

Collects real-time statistics for video recording, disk storage, database counts, and playback latency.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from camera_analytics.recording.database import MetadataDatabase
from camera_analytics.recording.playback import PlaybackService
from camera_analytics.recording.recorder import VideoSegmentRecorder
from camera_analytics.recording.storage_backend import StorageBackend

logger = logging.getLogger(__name__)


class RecordingHealthMonitor:
    """Observability & Health Monitoring Subsystem for Recording & Playback."""

    def __init__(
        self,
        recorder: VideoSegmentRecorder,
        storage_backend: StorageBackend,
        database: MetadataDatabase,
        playback_service: PlaybackService,
    ) -> None:
        self.recorder = recorder
        self.storage = storage_backend
        self.db = database
        self.playback = playback_service

    def get_health_report(self) -> dict[str, Any]:
        """Generate comprehensive observable health report."""
        storage_stats = self.storage.get_stats()
        db_counts = self.db.count_summary()

        return {
            "recorder": {
                "active": self.recorder.is_active,
                "camera_id": self.recorder.camera_id,
                "current_segment_id": self.recorder.current_segment_id,
                "frames_written": self.recorder._frames_written,
                "dropped_frames": self.recorder._dropped_frames,
                "fps": self.recorder.fps,
                "resolution": list(self.recorder.resolution),
            },
            "storage": storage_stats.to_dict(),
            "database": db_counts,
            "playback": {
                "avg_lookup_time_ms": round(self.playback.avg_lookup_time_ms, 2),
                "lookup_count": self.playback._lookup_count,
            },
        }
