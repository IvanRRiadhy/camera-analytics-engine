"""
Scene Domain Models Package.

Provides immutable data models representing a complete snapshot of world state for a single video frame:
    - SceneMetadata (UUID, Timestamp, FrameIndex, ProcessingTime, FrameworkVersion, CameraId)
    - SceneStatistics (ActiveTrackCount, ZoneCount, FPS, FrameLatency, AnalyticsExecutionTime)
    - Scene (Immutable Snapshot of World State containing CameraEntity, FrameEntity, Tracks, Zones)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

from camera_analytics.entities.models import (
    CameraEntity,
    FrameEntity,
    TrackEntity,
    ZoneEntity,
)


@dataclass(frozen=True, slots=True)
class SceneMetadata:
    """Immutable metadata identifier and timing information for a Scene snapshot."""

    scene_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = 0.0
    frame_index: int = 0
    processing_time_ms: float = 0.0
    framework_version: str = "v1.0.0"
    camera_id: str = "default_cam"

    def to_dict(self) -> dict[str, Any]:
        """Convert SceneMetadata to dictionary."""
        return {
            "scene_id": self.scene_id,
            "timestamp": round(self.timestamp, 3),
            "frame_index": self.frame_index,
            "processing_time_ms": round(self.processing_time_ms, 2),
            "framework_version": self.framework_version,
            "camera_id": self.camera_id,
        }


@dataclass(frozen=True, slots=True)
class SceneStatistics:
    """Immutable runtime statistics snapshot associated with a Scene."""

    active_track_count: int = 0
    zone_count: int = 0
    fps: float = 0.0
    frame_latency_ms: float = 0.0
    analytics_execution_time_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert SceneStatistics to dictionary."""
        return {
            "active_track_count": self.active_track_count,
            "zone_count": self.zone_count,
            "fps": round(self.fps, 1),
            "frame_latency_ms": round(self.frame_latency_ms, 2),
            "analytics_execution_time_ms": round(self.analytics_execution_time_ms, 2),
        }


@dataclass(frozen=True, slots=True)
class Scene:
    """Immutable Snapshot of World State for a single video frame.

    Serves as the primary READ-ONLY domain contract passed to all Analytics Modules.
    Modules access data via `scene.tracks`, `scene.zones`, `scene.camera`, `scene.frame`.

    Attempts to mutate attributes (e.g. `scene.camera = ...`) raise FrozenInstanceError.
    """

    camera: CameraEntity
    frame: FrameEntity
    tracks: tuple[TrackEntity, ...] = field(default_factory=tuple)
    zones: tuple[ZoneEntity, ...] = field(default_factory=tuple)
    statistics: SceneStatistics = field(default_factory=SceneStatistics)
    metadata: SceneMetadata = field(default_factory=SceneMetadata)
    extensions: dict[str, Any] = field(default_factory=dict)

    def get_track_by_id(self, track_id: int) -> Optional[TrackEntity]:
        """Lookup a TrackEntity by track_id.

        Args:
            track_id: Integer track ID.

        Returns:
            TrackEntity if found, None otherwise.
        """
        for t in self.tracks:
            if t.track_id == track_id:
                return t
        return None

    def get_zone_by_id(self, zone_id: str) -> Optional[ZoneEntity]:
        """Lookup a ZoneEntity by zone_id.

        Args:
            zone_id: String zone ID.

        Returns:
            ZoneEntity if found, None otherwise.
        """
        for z in self.zones:
            if z.zone_id == zone_id:
                return z
        return None

    def to_dict(self) -> dict[str, Any]:
        """Convert Scene to clean dictionary representation."""
        return {
            "metadata": self.metadata.to_dict(),
            "statistics": self.statistics.to_dict(),
            "camera": self.camera.to_dict(),
            "frame": self.frame.to_dict(),
            "tracks": [t.to_dict() for t in self.tracks],
            "zones": [z.to_dict() for z in self.zones],
            "extensions": self.extensions,
        }
