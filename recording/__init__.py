"""
Enterprise Recording & Playback Service Package.

Provides continuous video segment recording, metadata indexing, snapshot generation,
index-driven timeline playback, storage retention cleanup, and incident investigation APIs.
"""

from camera_analytics.recording.database import MetadataDatabase
from camera_analytics.recording.event_recorder import EventRecorder
from camera_analytics.recording.health import RecordingHealthMonitor
from camera_analytics.recording.investigation_api import InvestigationAPI
from camera_analytics.recording.playback import PlaybackService
from camera_analytics.recording.recorder import VideoSegmentRecorder
from camera_analytics.recording.schema import (
    EventReference,
    PlaybackSeekResult,
    RecordingSegment,
    SnapshotMetadata,
    StorageStats,
    TimelineEntry,
)
from camera_analytics.recording.segment_index import SegmentIndexer
from camera_analytics.recording.snapshot_generator import SnapshotGenerator
from camera_analytics.recording.storage_backend import (
    LocalStorageBackend,
    StorageBackend,
)
from camera_analytics.recording.timeline import TimelineBuilder

from camera_analytics.recording.overlay import DebugOverlayConfig, DebugVisualizationOverlay

__all__ = [
    "RecordingSegment",
    "EventReference",
    "SnapshotMetadata",
    "TimelineEntry",
    "PlaybackSeekResult",
    "StorageStats",
    "StorageBackend",
    "LocalStorageBackend",
    "MetadataDatabase",
    "SegmentIndexer",
    "VideoSegmentRecorder",
    "SnapshotGenerator",
    "EventRecorder",
    "TimelineBuilder",
    "PlaybackService",
    "InvestigationAPI",
    "RecordingHealthMonitor",
    "DebugVisualizationOverlay",
    "DebugOverlayConfig",
]
