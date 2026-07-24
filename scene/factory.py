"""
Scene Factory Component.

Constructs an immutable Scene snapshot directly from framework Runtime objects (RuntimeState, FrameContext, ZoneEngineResult).
Modul Analytics does not need to interact with or know about RuntimeState or ZoneEngine.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Optional, Sequence

from camera_analytics.entities.factory import EntityFactory
from camera_analytics.entities.models import ZoneState
from camera_analytics.scene.builder import SceneBuilder
from camera_analytics.scene.models import Scene, SceneMetadata, SceneStatistics

if TYPE_CHECKING:
    from camera_analytics.core.frame_context import FrameContext
    from camera_analytics.core.runtime import RuntimeState
    from camera_analytics.core.zone_engine import ZoneEngineResult
    from camera_analytics.models.zone import Zone


class SceneFactory:
    """Factory for manufacturing immutable Scene snapshots directly from Vision Engine Runtime objects."""

    @classmethod
    def create_scene(
        cls,
        runtime_state: Optional[RuntimeState] = None,
        frame_context: Optional[FrameContext] = None,
        zone_result: Optional[ZoneEngineResult] = None,
        zones: Optional[Sequence[Zone]] = None,
        frame_index: int = 0,
        timestamp: float = 0.0,
    ) -> Scene:
        """Construct an immutable Scene snapshot from Runtime components.

        Args:
            runtime_state: RuntimeState instance.
            frame_context: Optional FrameContext instance.
            zone_result: Optional ZoneEngineResult spatial evaluation instance.
            zones: Optional list of Zone model definitions.
            frame_index: Fallback frame index.
            timestamp: Fallback frame timestamp.

        Returns:
            Immutable Scene snapshot ready for Analytics Runtime processing.
        """
        t0 = time.monotonic()
        builder = SceneBuilder()

        # 1. Camera Entity
        if runtime_state and runtime_state.camera:
            cam_ent = EntityFactory.create_camera_entity(runtime_state.camera)
            builder.set_camera(cam_ent)

        # 2. Frame Entity
        frame_ent = EntityFactory.create_frame_entity(
            frame_context=frame_context,
            frame_index=frame_index,
            timestamp=timestamp,
        )
        builder.set_frame(frame_ent)

        # 3. Track Entities
        active_tracks = []
        if runtime_state and runtime_state.track_manager:
            active_tracks = runtime_state.track_manager.get_active()

        track_entities = [EntityFactory.create_track_entity(t) for t in active_tracks]
        builder.set_tracks(track_entities)

        # 4. Zone Entities
        zone_entities = []
        target_zones = zones or (runtime_state.camera.zones if runtime_state and runtime_state.camera else [])

        for zone in target_zones:
            current_state = ZoneState.OUTSIDE
            dwell_frames = 0

            # Determine spatial state from zone_result if available
            if zone_result:
                if zone_result.zone_occupancy and zone.zone_id in zone_result.zone_occupancy:
                    occ_tracks = zone_result.zone_occupancy[zone.zone_id]
                    if occ_tracks:
                        current_state = ZoneState.INSIDE

                if zone_result.track_states:
                    for trk_id, z_map in zone_result.track_states.items():
                        if zone.zone_id in z_map:
                            state_enum = z_map[zone.zone_id]
                            state_name = state_enum.name if hasattr(state_enum, "name") else str(state_enum)
                            if state_name == "ENTER":
                                current_state = ZoneState.ENTER
                            elif state_name == "EXIT":
                                current_state = ZoneState.EXIT
                            elif state_name == "INSIDE" and current_state != ZoneState.ENTER:
                                current_state = ZoneState.INSIDE

            z_ent = EntityFactory.create_zone_entity(
                zone=zone,
                current_state=current_state,
                dwell_frames=dwell_frames,
            )
            zone_entities.append(z_ent)

        builder.set_zones(zone_entities)

        t1 = time.monotonic()
        processing_ms = (t1 - t0) * 1000.0

        camera_id = builder._camera.camera_id if builder._camera else "default_cam"
        metadata = SceneMetadata(
            timestamp=frame_ent.timestamp,
            frame_index=frame_ent.frame_index,
            processing_time_ms=processing_ms,
            camera_id=camera_id,
        )
        builder.set_metadata(metadata)

        statistics = SceneStatistics(
            active_track_count=len(track_entities),
            zone_count=len(zone_entities),
            fps=frame_ent.fps,
            frame_latency_ms=frame_ent.latency_ms,
            analytics_execution_time_ms=processing_ms,
        )
        builder.set_statistics(statistics)

        return builder.build()
