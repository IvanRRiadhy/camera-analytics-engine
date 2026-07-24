"""
Runtime state.

Persistent cross-frame state container that lives for the entire
pipeline lifetime. Owns the TrackManager, Camera, EventBus, and
zone definitions.

Design decisions:
    - No ``shared_state: dict`` — inter-module communication uses
      typed ModuleState (exposed by each module) and TrackFeatureStore
      (per-track data), not an untyped global dict.
    - RuntimeState is NOT passed to modules via FrameContext. The
      Pipeline owns it and uses it to build each FrameContext.
    - Modules never see or mutate RuntimeState directly.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from camera_analytics.core.config import Config
from camera_analytics.core.events import EventBus
from camera_analytics.core.track_manager import TrackManager
from camera_analytics.models.camera import Camera
from camera_analytics.models.zone import Zone

logger = logging.getLogger(__name__)


class RuntimeState:
    """Persistent state container for the analytics pipeline.

    Created once when the Pipeline starts. Destroyed when the Pipeline
    stops. Modules never receive a reference to RuntimeState — the
    Pipeline uses it internally to construct FrameContext objects and
    manage track lifecycle.

    Attributes:
        config: Global framework configuration.
        event_bus: Shared event bus for publishing/subscribing events.
        track_manager: Centralized track lifecycle manager.
        camera: Camera configuration (source, resolution, zones).
        zones: Dictionary of zones extracted from camera config.

    Args:
        config: The global Config instance.
        event_bus: The shared EventBus instance.
        camera: The Camera configuration.
        track_manager_kwargs: Optional overrides for TrackManager
            constructor (max_history_length, confirm_after_n, max_lost_age).

    Example::

        runtime = RuntimeState(
            config=config,
            event_bus=event_bus,
            camera=camera,
        )

        # Pipeline uses runtime to build each frame's context
        context = build_frame_context(
            frame_id=runtime.total_frames,
            tracks=runtime.track_manager.get_active(),
            zones=runtime.zones,
            ...
        )
    """

    def __init__(
        self,
        config: Config,
        event_bus: EventBus,
        camera: Camera,
        track_manager_kwargs: Optional[dict] = None,
    ) -> None:
        self._config = config
        self._event_bus = event_bus
        self._camera = camera
        self._start_time: float = time.monotonic()
        self._total_frames: int = 0

        # Build TrackManager with config overrides
        tm_kwargs = track_manager_kwargs or {}
        tm_defaults = {
            "max_history_length": int(
                config.get("track_manager.max_history_length", 150)
            ),
            "confirm_after_n": int(
                config.get("track_manager.confirm_after_n", 3)
            ),
            "max_lost_age": int(
                config.get("track_manager.max_lost_age", 30)
            ),
        }
        tm_defaults.update(tm_kwargs)
        self._track_manager = TrackManager(**tm_defaults)

        # Extract zones from camera
        self._zones: dict[str, Zone] = dict(camera.zones)

        # Archive pruning config
        self._archive_prune_interval: int = int(
            config.get("track_manager.archive_prune_interval", 300)
        )
        self._max_archived: int = int(
            config.get("track_manager.max_archived", 1000)
        )

        logger.info(
            "RuntimeState initialized (camera=%s, zones=%d, "
            "history_len=%d, confirm_after=%d, max_lost=%d)",
            camera.camera_id,
            len(self._zones),
            tm_defaults["max_history_length"],
            tm_defaults["confirm_after_n"],
            tm_defaults["max_lost_age"],
        )

    # --- Accessors ---

    @property
    def config(self) -> Config:
        """Global framework configuration."""
        return self._config

    @property
    def event_bus(self) -> EventBus:
        """Shared event bus."""
        return self._event_bus

    @property
    def track_manager(self) -> TrackManager:
        """Centralized track lifecycle manager."""
        return self._track_manager

    @property
    def camera(self) -> Camera:
        """Camera configuration."""
        return self._camera

    @property
    def zones(self) -> dict[str, Zone]:
        """Dictionary of zones (keyed by zone_id)."""
        return self._zones

    # --- Timing ---

    @property
    def start_time(self) -> float:
        """Monotonic timestamp when the pipeline started."""
        return self._start_time

    @property
    def elapsed_time(self) -> float:
        """Seconds elapsed since pipeline start."""
        return time.monotonic() - self._start_time

    @property
    def current_timestamp(self) -> float:
        """Current elapsed timestamp (alias for elapsed_time)."""
        return self.elapsed_time

    # --- Frame Counting ---

    @property
    def total_frames(self) -> int:
        """Total frames processed so far."""
        return self._total_frames

    def increment_frame(self) -> int:
        """Increment and return the frame counter.

        Called by the Pipeline at the start of each frame.

        Returns:
            The new frame count (1-indexed).
        """
        self._total_frames += 1
        return self._total_frames

    # --- Maintenance ---

    def run_maintenance(self) -> None:
        """Run periodic maintenance tasks.

        Called by the Pipeline at configurable intervals.
        Currently prunes the track archive.
        """
        if (
            self._total_frames > 0
            and self._total_frames % self._archive_prune_interval == 0
        ):
            pruned = self._track_manager.prune_archive(self._max_archived)
            if pruned > 0:
                logger.info(
                    "Maintenance: pruned %d archived tracks at frame %d",
                    pruned,
                    self._total_frames,
                )

    # --- Zone Management ---

    def add_zone(self, zone: Zone) -> None:
        """Add a zone to the runtime.

        Args:
            zone: The zone to add.

        Raises:
            ValueError: If a zone with the same ID already exists.
        """
        if zone.zone_id in self._zones:
            raise ValueError(
                f"Zone '{zone.zone_id}' already exists in runtime."
            )
        self._zones[zone.zone_id] = zone
        self._camera.add_zone(zone)

    def remove_zone(self, zone_id: str) -> Optional[Zone]:
        """Remove a zone from the runtime.

        Args:
            zone_id: The zone ID to remove.

        Returns:
            The removed Zone, or None if not found.
        """
        zone = self._zones.pop(zone_id, None)
        if zone is not None:
            self._camera.remove_zone(zone_id)
        return zone

    # --- Summary ---

    def get_summary(self) -> dict:
        """Get a summary of the current runtime state.

        Returns:
            Dictionary with runtime metrics.
        """
        return {
            "camera_id": self._camera.camera_id,
            "total_frames": self._total_frames,
            "elapsed_time": round(self.elapsed_time, 2),
            "active_tracks": self._track_manager.active_count,
            "confirmed_tracks": self._track_manager.confirmed_count,
            "archived_tracks": self._track_manager.archived_count,
            "total_tracks_created": self._track_manager.total_created,
            "zones": list(self._zones.keys()),
        }

    def __repr__(self) -> str:
        return (
            f"RuntimeState("
            f"camera={self._camera.camera_id}, "
            f"frames={self._total_frames}, "
            f"tracks={self._track_manager})"
        )
