"""
Scene Builder Component.

Provides a step-by-step fluent builder pattern for constructing immutable Scene domain snapshots.
"""

from __future__ import annotations

import time
from typing import Any, Optional, Sequence

from camera_analytics.entities.models import (
    CameraEntity,
    FrameEntity,
    TrackEntity,
    ZoneEntity,
)
from camera_analytics.scene.models import (
    Scene,
    SceneMetadata,
    SceneStatistics,
)


class SceneBuilder:
    """Fluent Builder for constructing immutable Scene objects.

    Usage::

        scene = (
            SceneBuilder()
            .set_camera(camera_entity)
            .set_frame(frame_entity)
            .set_tracks(track_entities)
            .set_zones(zone_entities)
            .build()
        )
    """

    def __init__(self) -> None:
        self._camera: Optional[CameraEntity] = None
        self._frame: Optional[FrameEntity] = None
        self._tracks: list[TrackEntity] = []
        self._zones: list[ZoneEntity] = []
        self._statistics: Optional[SceneStatistics] = None
        self._metadata: Optional[SceneMetadata] = None
        self._extensions: dict[str, Any] = {}
        self._start_time = time.monotonic()

    def set_camera(self, camera: CameraEntity) -> SceneBuilder:
        """Set CameraEntity."""
        self._camera = camera
        return self

    def set_frame(self, frame: FrameEntity) -> SceneBuilder:
        """Set FrameEntity."""
        self._frame = frame
        return self

    def add_track(self, track: TrackEntity) -> SceneBuilder:
        """Add a single TrackEntity."""
        self._tracks.append(track)
        return self

    def set_tracks(self, tracks: Sequence[TrackEntity]) -> SceneBuilder:
        """Set collection of TrackEntity objects."""
        self._tracks = list(tracks)
        return self

    def add_zone(self, zone: ZoneEntity) -> SceneBuilder:
        """Add a single ZoneEntity."""
        self._zones.append(zone)
        return self

    def set_zones(self, zones: Sequence[ZoneEntity]) -> SceneBuilder:
        """Set collection of ZoneEntity objects."""
        self._zones = list(zones)
        return self

    def set_statistics(self, statistics: SceneStatistics) -> SceneBuilder:
        """Set explicit SceneStatistics instance."""
        self._statistics = statistics
        return self

    def set_metadata(self, metadata: SceneMetadata) -> SceneBuilder:
        """Set explicit SceneMetadata instance."""
        self._metadata = metadata
        return self

    def add_extension(self, key: str, value: Any) -> SceneBuilder:
        """Add a custom extension value (Future Ready)."""
        self._extensions[key] = value
        return self

    def build(self) -> Scene:
        """Assemble and construct immutable Scene snapshot instance.

        Returns:
            Immutable Scene object.
        """
        camera = self._camera or CameraEntity(camera_id="default_cam", camera_name="Default Camera")
        frame = self._frame or FrameEntity(frame_index=0, timestamp=0.0, frame_width=1920, frame_height=1080)

        elapsed_ms = (time.monotonic() - self._start_time) * 1000.0

        metadata = self._metadata or SceneMetadata(
            timestamp=frame.timestamp,
            frame_index=frame.frame_index,
            processing_time_ms=elapsed_ms,
            camera_id=camera.camera_id,
        )

        statistics = self._statistics or SceneStatistics(
            active_track_count=len(self._tracks),
            zone_count=len(self._zones),
            fps=frame.fps,
            frame_latency_ms=frame.latency_ms,
            analytics_execution_time_ms=elapsed_ms,
        )

        return Scene(
            camera=camera,
            frame=frame,
            tracks=tuple(self._tracks),
            zones=tuple(self._zones),
            statistics=statistics,
            metadata=metadata,
            extensions=dict(self._extensions),
        )
