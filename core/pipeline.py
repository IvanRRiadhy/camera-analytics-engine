"""
Analytics pipeline.

The central orchestrator that manages the lifecycle of analytics modules
and coordinates frame-by-frame processing. The Pipeline is the main
entry point for running camera analytics.

Sprint 2 changes:
    - Pipeline now owns RuntimeState (TrackManager, Camera, EventBus).
    - process() builds a FrameContext each frame and passes it to modules.
    - Per-module process_interval support (not every module runs every frame).
    - Accepts optional DetectorPort / TrackerPort for AI model integration.
    - get_module_output() for queryable module state.

Typical usage::

    camera = Camera(camera_id="cam_01", name="Lobby", source="rtsp://...")
    config = Config.from_dict({...})

    pipeline = Pipeline(config, camera)
    pipeline.register(PeopleAnalytics())
    pipeline.start()

    for frame in video_source:
        context = pipeline.process(frame, tracker_results)

    pipeline.stop()
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Optional

import numpy as np

from camera_analytics.core.base_module import (
    AnalyticsModule,
    ModuleOutput,
)
from camera_analytics.core.config import Config
from camera_analytics.core.detection_set import DetectionSet
from camera_analytics.core.events import EventBus
from camera_analytics.core.frame_context import FrameContext, build_frame_context
from camera_analytics.core.registry import ModuleRegistry
from camera_analytics.core.runtime import RuntimeState
from camera_analytics.core.track_manager import TrackerResult
from camera_analytics.models.camera import Camera
from camera_analytics.models.detection import Detection

if TYPE_CHECKING:
    from numpy.typing import NDArray

logger = logging.getLogger(__name__)


class PipelineState(Enum):
    """Lifecycle state of the pipeline.

    Attributes:
        IDLE: Pipeline created but not started.
        RUNNING: Pipeline is actively processing frames.
        PAUSED: Pipeline processing is temporarily suspended.
        STOPPED: Pipeline has been shut down.
    """

    IDLE = auto()
    RUNNING = auto()
    PAUSED = auto()
    STOPPED = auto()


@dataclass(slots=True)
class PipelineStats:
    """Runtime statistics for the pipeline.

    Accumulated during processing for performance monitoring.

    Attributes:
        total_frames: Total number of frames processed.
        total_time_sec: Total processing time in seconds.
        last_frame_time_sec: Time to process the most recent frame.
        module_times: Per-module cumulative processing time in seconds.
    """

    total_frames: int = 0
    total_time_sec: float = 0.0
    last_frame_time_sec: float = 0.0
    module_times: dict[str, float] = field(default_factory=dict)

    @property
    def avg_frame_time_sec(self) -> float:
        """Average time per frame in seconds."""
        if self.total_frames == 0:
            return 0.0
        return self.total_time_sec / self.total_frames

    @property
    def avg_fps(self) -> float:
        """Average frames per second."""
        avg = self.avg_frame_time_sec
        if avg == 0.0:
            return 0.0
        return 1.0 / avg


class Pipeline:
    """Central analytics pipeline orchestrator.

    Manages the lifecycle of analytics modules and coordinates
    frame-by-frame processing. Owns a RuntimeState that persists
    across frames and builds a FrameContext for each frame.

    The pipeline guarantees:
        - Modules are initialized in registration order.
        - Modules are processed in registration order each frame.
        - Modules are shut down in reverse registration order.
        - A single module's error does not crash the pipeline.
        - Per-module process_interval is respected.

    Args:
        config: Global framework configuration.
        camera: Camera configuration for this pipeline.
        event_bus: Optional shared EventBus. Created automatically if not provided.

    Example::

        config = Config.from_dict({
            "modules": {
                "people_analytics": {"enabled": True, "crowd_threshold": 5}
            }
        })
        camera = Camera(camera_id="cam_01", name="Lobby", source="video.mp4")

        pipeline = Pipeline(config, camera)
        pipeline.register(PeopleAnalytics())
        pipeline.start()

        for frame in frames:
            context = pipeline.process(frame, tracker_results)

        stats = pipeline.stop()
    """

    def __init__(
        self,
        config: Config,
        camera: Camera,
        event_bus: Optional[EventBus] = None,
    ) -> None:
        self._config = config
        self._camera = camera
        self._event_bus = event_bus if event_bus is not None else EventBus()
        self._registry = ModuleRegistry()
        self._state = PipelineState.IDLE
        self._stats = PipelineStats()
        self._runtime: Optional[RuntimeState] = None

    # --- Module Registration ---

    def register(self, module: AnalyticsModule) -> None:
        """Register an analytics module to the pipeline.

        Modules must be registered before calling start().

        Args:
            module: The analytics module instance to register.

        Raises:
            RuntimeError: If the pipeline is already running.
            RegistryError: If a module with the same name exists.
        """
        if self._state == PipelineState.RUNNING:
            raise RuntimeError(
                "Cannot register modules while the pipeline is running. "
                "Stop the pipeline first."
            )

        self._registry.register(module)
        logger.info(
            "Module '%s' registered to pipeline", module.name
        )

    def unregister(self, module_name: str) -> Optional[AnalyticsModule]:
        """Unregister a module from the pipeline by name.

        If the module is currently running, it will be shut down first.
        Also cleans up the module's feature namespace from all tracks.

        Args:
            module_name: Name of the module to remove.

        Returns:
            The removed module instance, or None if not found.
        """
        module = self._registry.get(module_name)

        if module is not None and module.is_ready:
            module.shutdown()

        # Clean up track features for this module
        if self._runtime is not None:
            self._runtime.track_manager.clear_features_namespace(module_name)

        return self._registry.unregister(module_name)

    # --- Lifecycle ---

    def start(self) -> None:
        """Start the pipeline and initialize all registered modules.

        Creates the RuntimeState, validates dependencies, then
        initializes each module in registration order.

        Raises:
            RuntimeError: If the pipeline is not in IDLE state.
            RuntimeError: If module dependencies are not satisfied.
        """
        if self._state != PipelineState.IDLE:
            raise RuntimeError(
                f"Pipeline cannot start from state {self._state.name}. "
                f"Must be IDLE."
            )

        # Create RuntimeState
        self._runtime = RuntimeState(
            config=self._config,
            event_bus=self._event_bus,
            camera=self._camera,
        )

        # Validate dependencies
        dep_errors = self._registry.validate_dependencies()
        if dep_errors:
            raise RuntimeError(
                "Unsatisfied module dependencies:\n"
                + "\n".join(f"  - {e}" for e in dep_errors)
            )

        # Initialize modules in registration order
        for module in self._registry.get_all():
            module_config = self._config.get_module_config(module.name)

            if not module_config.enabled:
                logger.info(
                    "Skipping disabled module '%s'", module.name
                )
                continue

            module.initialize(self._config, self._event_bus)

        self._state = PipelineState.RUNNING
        self._stats = PipelineStats()

        logger.info(
            "Pipeline started with %d module(s): %s",
            self._registry.count,
            self._registry.module_names,
        )

    def stop(self) -> PipelineStats:
        """Stop the pipeline and shut down all modules.

        Modules are shut down in reverse registration order.
        RuntimeState is released.

        Returns:
            Final PipelineStats with accumulated metrics.
        """
        if self._state == PipelineState.STOPPED:
            logger.warning("Pipeline is already stopped")
            return self._stats

        # Shutdown in reverse order
        for module in reversed(self._registry.get_all()):
            module.shutdown()

        self._state = PipelineState.STOPPED

        total_frames = self._runtime.total_frames if self._runtime else 0
        logger.info(
            "Pipeline stopped -- %d frames processed in %.2fs (avg %.1f FPS)",
            self._stats.total_frames,
            self._stats.total_time_sec,
            self._stats.avg_fps,
        )

        return self._stats

    def pause(self) -> None:
        """Pause frame processing (modules remain initialized)."""
        if self._state == PipelineState.RUNNING:
            self._state = PipelineState.PAUSED
            logger.info("Pipeline paused")

    def resume(self) -> None:
        """Resume frame processing after a pause."""
        if self._state == PipelineState.PAUSED:
            self._state = PipelineState.RUNNING
            logger.info("Pipeline resumed")

    # --- Frame Processing ---

    def process(
        self,
        frame: NDArray[np.uint8],
        tracker_results: Optional[list[TrackerResult]] = None,
    ) -> Optional[FrameContext]:
        """Process a single video frame through all enabled modules.

        Builds a FrameContext from the frame, updates TrackManager with
        tracker results, and dispatches the context to each enabled
        module (respecting per-module process_interval).

        Args:
            frame: Current video frame (BGR, HxWx3 numpy array).
            tracker_results: Optional tracker output. If None, tracks
                are not updated this frame.

        Returns:
            The FrameContext for this frame, or None if pipeline is
            not running.
        """
        if self._state != PipelineState.RUNNING or self._runtime is None:
            return None

        frame_id = self._runtime.increment_frame()

        # Update TrackManager with tracker results
        if tracker_results is not None:
            self._runtime.track_manager.update_from_tracker(
                tracker_results, frame_id
            )

        # Run periodic maintenance (archive pruning)
        self._runtime.run_maintenance()

        # Build detections from tracker results
        detections = DetectionSet(
            [r.detection for r in tracker_results]
            if tracker_results
            else []
        )

        # Process ZoneEngine spatial evaluation
        zone_list = list(self._runtime.zones.values())
        zone_results = self._runtime.zone_engine.process(
            tracks=self._runtime.track_manager.get_active(),
            zones=zone_list,
            frame_index=frame_id,
            timestamp=self._runtime.elapsed_time,
        )

        # Build FrameContext
        context = build_frame_context(
            frame_id=frame_id,
            timestamp=self._runtime.elapsed_time,
            image=frame,
            camera_id=self._camera.camera_id,
            detections=detections,
            tracks=self._runtime.track_manager.get_active(),
            zones=self._runtime.zones,
        )
        object.__setattr__(context, "zone_results", zone_results)

        # Dispatch to modules
        frame_start = time.perf_counter()

        for module in self._registry.get_enabled():
            # Respect per-module process_interval
            if module.process_interval > 1:
                if frame_id % module.process_interval != 0:
                    continue

            module_start = time.perf_counter()
            module.process(context)
            module_elapsed = time.perf_counter() - module_start

            # Accumulate per-module timing
            self._stats.module_times[module.name] = (
                self._stats.module_times.get(module.name, 0.0)
                + module_elapsed
            )

        frame_elapsed = time.perf_counter() - frame_start

        self._stats.total_frames += 1
        self._stats.total_time_sec += frame_elapsed
        self._stats.last_frame_time_sec = frame_elapsed

        return context

    # --- Module Output Query ---

    def get_module_output(self, module_name: str) -> Optional[ModuleOutput]:
        """Query the current state of an analytics module.

        Allows the Rule Engine, Dashboard, or API to inspect a module's
        current analytics state without relying on events.

        Args:
            module_name: Name of the module to query.

        Returns:
            The module's ModuleOutput, or None if not found/not ready.
        """
        module = self._registry.get(module_name)
        if module is None or not module.is_ready:
            return None
        return module.get_output()

    def get_all_module_outputs(self) -> dict[str, ModuleOutput]:
        """Query current state of all enabled modules.

        Returns:
            Dictionary of module_name -> ModuleOutput.
        """
        outputs: dict[str, ModuleOutput] = {}
        for module in self._registry.get_enabled():
            try:
                outputs[module.name] = module.get_output()
            except Exception:
                logger.exception(
                    "Failed to get output from module '%s'", module.name
                )
        return outputs

    # --- Accessors ---

    @property
    def state(self) -> PipelineState:
        """Current pipeline state."""
        return self._state

    @property
    def is_running(self) -> bool:
        """Whether the pipeline is actively processing."""
        return self._state == PipelineState.RUNNING

    @property
    def stats(self) -> PipelineStats:
        """Current pipeline statistics."""
        return self._stats

    @property
    def event_bus(self) -> EventBus:
        """The shared EventBus instance."""
        return self._event_bus

    @property
    def registry(self) -> ModuleRegistry:
        """The module registry."""
        return self._registry

    @property
    def runtime(self) -> Optional[RuntimeState]:
        """The RuntimeState (available after start)."""
        return self._runtime

    @property
    def frame_index(self) -> int:
        """Current frame counter."""
        if self._runtime is not None:
            return self._runtime.total_frames
        return 0

    @property
    def config(self) -> Config:
        """The global configuration."""
        return self._config
