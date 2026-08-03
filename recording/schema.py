"""
Recording & Playback Subsystem Schemas & Models.

Defines strongly typed data structures for video segments, event references,
snapshot metadata, timeline entries, playback seek results, and storage statistics.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(slots=True)
class RecordingSegment:
    """Indexed metadata for a single recorded video segment file.

    Attributes:
        segment_id: Unique string segment identifier.
        camera_id: Associated camera identifier.
        file_path: Absolute or relative file path to segment video.
        start_timestamp: Start timestamp of segment in UTC ISO8601 or epoch seconds.
        end_timestamp: End timestamp of segment.
        duration_sec: Segment duration in seconds.
        fps: Recording frame rate.
        resolution: Tuple of (width, height) in pixels.
        codec: Video codec (e.g. 'mp4v', 'avc1', 'h264').
        file_size_bytes: File size on disk in bytes.
        checksum: MD5 or SHA256 checksum string.
    """

    segment_id: str
    camera_id: str
    file_path: str
    start_timestamp: float
    end_timestamp: float
    duration_sec: float
    fps: float = 30.0
    resolution: tuple[int, int] = (1920, 1080)
    codec: str = "mp4v"
    file_size_bytes: int = 0
    checksum: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert RecordingSegment to dictionary."""
        return {
            "segment_id": self.segment_id,
            "camera_id": self.camera_id,
            "file_path": self.file_path,
            "start_timestamp": round(self.start_timestamp, 3),
            "end_timestamp": round(self.end_timestamp, 3),
            "duration_sec": round(self.duration_sec, 2),
            "fps": round(self.fps, 1),
            "resolution": list(self.resolution),
            "codec": self.codec,
            "file_size_bytes": self.file_size_bytes,
            "checksum": self.checksum,
        }


@dataclass(slots=True)
class EventReference:
    """Lightweight database reference to a StandardAnalyticsEvent.

    Attributes:
        event_id: Unique event UUID string.
        event_type: String classification (e.g. 'CROWD_ALERT').
        camera_id: Associated camera identifier.
        timestamp: Event timestamp in UTC seconds.
        segment_id: Associated recording segment ID.
        seek_offset_sec: Seek offset in seconds inside segment.
        frame_index: Sequential frame number.
        track_id: Optional associated track ID.
        zone_id: Optional associated zone ID.
        severity: Event severity ('INFO', 'WARNING', 'ALERT', 'CRITICAL').
        snapshot_path: Optional path to associated JPEG snapshot.
        message: Event description.
    """

    event_id: str
    event_type: str
    camera_id: str
    timestamp: float
    segment_id: str
    seek_offset_sec: float
    frame_index: int = 0
    track_id: Optional[int] = None
    zone_id: Optional[str] = None
    severity: str = "INFO"
    snapshot_path: Optional[str] = None
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert EventReference to dictionary."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "camera_id": self.camera_id,
            "timestamp": round(self.timestamp, 3),
            "segment_id": self.segment_id,
            "seek_offset_sec": round(self.seek_offset_sec, 2),
            "frame_index": self.frame_index,
            "track_id": self.track_id,
            "zone_id": self.zone_id,
            "severity": self.severity,
            "snapshot_path": self.snapshot_path,
            "message": self.message,
        }


@dataclass(slots=True)
class SnapshotMetadata:
    """Metadata for an event-triggered JPEG snapshot image.

    Attributes:
        snapshot_id: Unique snapshot identifier string.
        event_id: Associated event ID.
        camera_id: Associated camera ID.
        timestamp: Snapshot creation timestamp in UTC seconds.
        file_path: File path to saved JPEG image on disk.
        resolution: Tuple of (width, height) in pixels.
        quality: JPEG compression quality percentage (1-100).
    """

    snapshot_id: str
    event_id: str
    camera_id: str
    timestamp: float
    file_path: str
    resolution: tuple[int, int] = (1920, 1080)
    quality: int = 90

    def to_dict(self) -> dict[str, Any]:
        """Convert SnapshotMetadata to dictionary."""
        return {
            "snapshot_id": self.snapshot_id,
            "event_id": self.event_id,
            "camera_id": self.camera_id,
            "timestamp": round(self.timestamp, 3),
            "file_path": self.file_path,
            "resolution": list(self.resolution),
            "quality": self.quality,
        }


@dataclass(slots=True)
class TimelineEntry:
    """Chronological timeline entry for forensic investigation workflows."""

    entry_id: str
    timestamp: float
    event_type: str
    severity: str
    camera_id: str
    segment_id: str
    seek_offset_sec: float
    track_id: Optional[int] = None
    zone_id: Optional[str] = None
    snapshot_path: Optional[str] = None
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert TimelineEntry to dictionary."""
        return {
            "entry_id": self.entry_id,
            "timestamp": round(self.timestamp, 3),
            "event_type": self.event_type,
            "severity": self.severity,
            "camera_id": self.camera_id,
            "segment_id": self.segment_id,
            "seek_offset_sec": round(self.seek_offset_sec, 2),
            "track_id": self.track_id,
            "zone_id": self.zone_id,
            "snapshot_path": self.snapshot_path,
            "message": self.message,
        }


@dataclass(slots=True)
class PlaybackSeekResult:
    """Index-driven playback seek resolution result.

    Attributes:
        camera_id: Target camera ID.
        requested_timestamp: Requested lookup timestamp.
        segment_id: Matching video segment ID.
        segment_path: Path to target segment file.
        seek_offset_sec: Exact seek offset inside segment in seconds.
        exact_match: True if requested_timestamp falls strictly within segment.
        near_timestamp: Actual timestamp found in segment.
    """

    camera_id: str
    requested_timestamp: float
    segment_id: str
    segment_path: str
    seek_offset_sec: float
    exact_match: bool = True
    near_timestamp: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert PlaybackSeekResult to dictionary."""
        return {
            "camera_id": self.camera_id,
            "requested_timestamp": round(self.requested_timestamp, 3),
            "segment_id": self.segment_id,
            "segment_path": self.segment_path,
            "seek_offset_sec": round(self.seek_offset_sec, 2),
            "exact_match": self.exact_match,
            "near_timestamp": round(self.near_timestamp, 3),
        }


@dataclass(slots=True)
class StorageStats:
    """Storage capacity and health statistics."""

    total_space_bytes: int = 0
    used_space_bytes: int = 0
    free_space_bytes: int = 0
    recordings_bytes: int = 0
    snapshots_bytes: int = 0
    segment_count: int = 0
    snapshot_count: int = 0
    event_count: int = 0
    retention_days: int = 30

    def to_dict(self) -> dict[str, Any]:
        """Convert StorageStats to dictionary."""
        return {
            "total_space_gb": round(self.total_space_bytes / (1024**3), 2),
            "used_space_gb": round(self.used_space_bytes / (1024**3), 2),
            "free_space_gb": round(self.free_space_bytes / (1024**3), 2),
            "recordings_mb": round(self.recordings_bytes / (1024**2), 2),
            "snapshots_mb": round(self.snapshots_bytes / (1024**2), 2),
            "segment_count": self.segment_count,
            "snapshot_count": self.snapshot_count,
            "event_count": self.event_count,
            "retention_days": self.retention_days,
        }
