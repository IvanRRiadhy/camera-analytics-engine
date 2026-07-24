"""
Base analytics module.

Defines the abstract interface that all analytics modules must implement.
Every module in the framework (PeopleAnalytics, PPEAnalytics, etc.)
inherits from AnalyticsModule and implements initialize(), process(),
and shutdown().

Sprint 2 changes:
    - on_process() now receives FrameContext instead of (frame, tracks, frame_index).
    - Added ModuleOutput abstract class for queryable module state.
    - Added process_interval support in ModuleInfo.
    - Renamed ModuleState enum to ModuleLifecycle to avoid clash with ModuleOutput.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Any, Optional

from camera_analytics.core.config import Config, ModuleConfig
from camera_analytics.core.events import EventBus
from camera_analytics.models.event import (
    EventCategory,
    EventSeverity,
    create_event,
)

if TYPE_CHECKING:
    from camera_analytics.core.frame_context import FrameContext


class ModuleLifecycle(Enum):
    """Lifecycle state of an analytics module.

    Attributes:
        CREATED: Module instantiated but not yet initialized.
        READY: Module initialized and ready to process frames.
        RUNNING: Module is actively processing.
        ERROR: Module encountered an error.
        STOPPED: Module has been shut down.
    """

    CREATED = auto()
    READY = auto()
    RUNNING = auto()
    ERROR = auto()
    STOPPED = auto()


@dataclass
class ModuleInfo:
    """Descriptive metadata about an analytics module.

    Used for logging, registration, and administrative purposes.

    Attributes:
        name: Unique module name (used as config key and event source).
        version: Semantic version string.
        description: Human-readable description of what this module does.
        dependencies: List of module names this module depends on.
        process_interval: Process every N frames (1 = every frame).
    """

    name: str
    version: str = "1.0.0"
    description: str = ""
    dependencies: list[str] = field(default_factory=list)
    process_interval: int = 1


@dataclass
class ModuleOutput:
    """Base class for queryable module state.

    Each analytics module exposes its current state through a
    ModuleOutput subclass. This enables the Rule Engine and Dashboard
    to query module state without relying solely on events.

    Subclasses should add typed fields specific to their analytics.

    Example::

        @dataclass
        class PeopleModuleOutput(ModuleOutput):
            current_count: int = 0
            zone_counts: dict[str, int] = field(default_factory=dict)
            crowd_active: bool = False

    Attributes:
        module_name: Name of the module that produced this output.
        last_frame_id: Frame ID when this output was last updated.
    """

    module_name: str = ""
    last_frame_id: int = 0


class AnalyticsModule(ABC):
    """Abstract base class for all analytics modules.

    Provides a standardized lifecycle (initialize -> process -> shutdown),
    access to the EventBus for publishing events, access to the
    module's configuration section, and queryable module output.

    Subclasses MUST implement:
        - module_info -> ModuleInfo (property)
        - on_initialize(config) -> None
        - on_process(context: FrameContext) -> None
        - on_shutdown() -> None
        - get_output() -> ModuleOutput

    Example::

        class PeopleAnalytics(AnalyticsModule):

            @property
            def module_info(self) -> ModuleInfo:
                return ModuleInfo(
                    name="people_analytics",
                    version="1.0.0",
                    description="People counting and tracking analytics.",
                    process_interval=1,
                )

            def on_initialize(self, config: ModuleConfig) -> None:
                self.threshold = config.get_float("confidence_threshold", 0.5)

            def on_process(self, context: FrameContext) -> None:
                people = context.person_tracks
                if len(people) > 10:
                    self.emit_event(
                        event_type="people.crowd_detected",
                        category=EventCategory.COUNTING,
                        severity=EventSeverity.WARNING,
                        frame_index=context.frame_id,
                        message=f"Crowd: {len(people)} people",
                    )

            def on_shutdown(self) -> None:
                pass

            def get_output(self) -> PeopleModuleOutput:
                return PeopleModuleOutput(
                    module_name=self.name,
                    current_count=self._count,
                )
    """

    def __init__(self) -> None:
        self._lifecycle: ModuleLifecycle = ModuleLifecycle.CREATED
        self._event_bus: Optional[EventBus] = None
        self._config: Optional[ModuleConfig] = None
        self._logger: logging.Logger = logging.getLogger(
            f"{__name__}.{self.__class__.__name__}"
        )
        self._frame_count: int = 0
        self._error_count: int = 0

    # --- Abstract Interface (subclasses MUST implement) ---

    @property
    @abstractmethod
    def module_info(self) -> ModuleInfo:
        """Return descriptive metadata about this module.

        Returns:
            ModuleInfo with name, version, description, and dependencies.
        """

    @abstractmethod
    def on_initialize(self, config: ModuleConfig) -> None:
        """Initialize module-specific resources.

        Called once when the pipeline starts. Use this to load models,
        set thresholds, or allocate resources.

        Args:
            config: Module-specific configuration section.
        """

    @abstractmethod
    def on_process(self, context: FrameContext) -> None:
        """Process a single video frame using the FrameContext.

        Called by the pipeline at the module's process_interval.
        This is where the module's core analytics logic lives.

        Args:
            context: Immutable per-frame data snapshot containing
                     image, detections, tracks, zones, and metadata.
        """

    @abstractmethod
    def on_shutdown(self) -> None:
        """Release module-specific resources.

        Called once when the pipeline stops. Use this to close files,
        release models, or flush buffers.
        """

    @abstractmethod
    def get_output(self) -> ModuleOutput:
        """Return the current queryable state of this module.

        Called by the Rule Engine, Dashboard, or other consumers
        to inspect the module's current analytics state.

        Returns:
            A ModuleOutput subclass with module-specific fields.
        """

    # --- Lifecycle Management (called by Pipeline) ---

    def initialize(self, config: Config, event_bus: EventBus) -> None:
        """Initialize this module. Called by the Pipeline.

        Extracts the module's config section and delegates to on_initialize().

        Args:
            config: Global framework configuration.
            event_bus: Shared event bus for publishing events.

        Raises:
            RuntimeError: If the module is not in CREATED state.
        """
        if self._lifecycle != ModuleLifecycle.CREATED:
            raise RuntimeError(
                f"Module '{self.name}' cannot be initialized "
                f"from state {self._lifecycle.name}."
            )

        self._event_bus = event_bus
        self._config = config.get_module_config(self.name)

        try:
            self.on_initialize(self._config)
            self._lifecycle = ModuleLifecycle.READY
            self._logger.info(
                "Module '%s' v%s initialized (interval=%d)",
                self.name,
                self.module_info.version,
                self.module_info.process_interval,
            )
        except Exception as exc:
            self._lifecycle = ModuleLifecycle.ERROR
            self._logger.exception(
                "Module '%s' failed to initialize: %s", self.name, exc
            )
            raise

    def process(self, context: FrameContext) -> None:
        """Process a frame context. Called by the Pipeline each frame.

        Delegates to on_process() and handles state transitions.

        Args:
            context: Immutable per-frame data snapshot.
        """
        if self._lifecycle not in (
            ModuleLifecycle.READY,
            ModuleLifecycle.RUNNING,
        ):
            return

        self._lifecycle = ModuleLifecycle.RUNNING

        try:
            self.on_process(context)
            self._frame_count += 1
        except Exception as exc:
            self._error_count += 1
            self._logger.exception(
                "Module '%s' error at frame %d: %s",
                self.name,
                context.frame_id,
                exc,
            )

    def shutdown(self) -> None:
        """Shut down this module. Called by the Pipeline.

        Delegates to on_shutdown() and transitions to STOPPED state.
        """
        if self._lifecycle == ModuleLifecycle.STOPPED:
            return

        try:
            self.on_shutdown()
        except Exception as exc:
            self._logger.exception(
                "Module '%s' error during shutdown: %s", self.name, exc
            )
        finally:
            self._lifecycle = ModuleLifecycle.STOPPED
            self._logger.info(
                "Module '%s' shut down (processed %d frames, %d errors)",
                self.name,
                self._frame_count,
                self._error_count,
            )

    # --- Convenience Properties ---

    @property
    def name(self) -> str:
        """Module name (shortcut to module_info.name)."""
        return self.module_info.name

    @property
    def lifecycle(self) -> ModuleLifecycle:
        """Current lifecycle state."""
        return self._lifecycle

    @property
    def is_ready(self) -> bool:
        """Whether the module is ready or running."""
        return self._lifecycle in (
            ModuleLifecycle.READY,
            ModuleLifecycle.RUNNING,
        )

    @property
    def process_interval(self) -> int:
        """How often this module should process (every N frames)."""
        return self.module_info.process_interval

    @property
    def config(self) -> Optional[ModuleConfig]:
        """Module's configuration section (available after initialize)."""
        return self._config

    @property
    def frame_count(self) -> int:
        """Number of frames processed by this module."""
        return self._frame_count

    @property
    def error_count(self) -> int:
        """Number of errors encountered during processing."""
        return self._error_count

    # --- Event Emission Helpers ---

    def emit_event(
        self,
        event_type: str,
        category: EventCategory,
        severity: EventSeverity,
        frame_index: int,
        message: str,
        track_id: Optional[int] = None,
        global_id: Optional[int] = None,
        zone_id: Optional[str] = None,
        data: Optional[dict[str, Any]] = None,
    ) -> None:
        """Publish an event through the EventBus.

        Convenience method that auto-fills the source_module field.

        Args:
            event_type: Specific event type string.
            category: Event category.
            severity: Event severity.
            frame_index: Current frame index.
            message: Human-readable event description.
            track_id: Optional track ID.
            global_id: Optional global ReID person ID.
            zone_id: Optional zone ID.
            data: Optional structured data payload.
        """
        if self._event_bus is None:
            self._logger.warning(
                "Cannot emit event '%s' -- EventBus not available.",
                event_type,
            )
            return

        event = create_event(
            event_type=event_type,
            category=category,
            severity=severity,
            source_module=self.name,
            frame_index=frame_index,
            message=message,
            track_id=track_id,
            global_id=global_id,
            zone_id=zone_id,
            data=data,
        )
        self._event_bus.publish(event)
