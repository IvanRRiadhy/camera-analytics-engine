"""
Analytics Module Base Contract.

Defines the abstract base class `AnalyticsModule` with full lifecycle contracts
and decoupled event callbacks for Track and Zone Engine spatial events.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Optional

from camera_analytics.sdk.models import AnalyticsContext, AnalyticsResult

if TYPE_CHECKING:
    from camera_analytics.core.zone_engine import ZoneEvent
    from camera_analytics.models.track import Track

logger = logging.getLogger(__name__)


class AnalyticsModule(ABC):
    """Abstract Base Class for all Analytics Modules in the platform.

    Provides standard lifecycle management (initialize, start, update, stop, dispose)
    and event callback hooks for track lifecycle and zone spatial events.

    Attributes:
        name: Unique string identifier of this analytics module.
        description: Brief human-readable description of the module.
    """

    def __init__(self, name: str, description: str = "") -> None:
        self._name = name
        self._description = description
        self._is_initialized = False
        self._is_running = False

    @property
    def name(self) -> str:
        """Module string identifier."""
        return self._name

    @property
    def description(self) -> str:
        """Module description."""
        return self._description

    @property
    def is_initialized(self) -> bool:
        """Whether the module has been initialized."""
        return self._is_initialized

    @property
    def is_running(self) -> bool:
        """Whether the module is actively running."""
        return self._is_running

    # --- Standard Module Lifecycle ---

    def initialize(self, context: AnalyticsContext) -> None:
        """Initialize the analytics module with initial context and configurations.

        Args:
            context: AnalyticsContext instance.
        """
        if self._is_initialized:
            return
        self.on_initialize(context)
        self._is_initialized = True
        logger.debug("AnalyticsModule '%s' initialized", self._name)

    def start(self) -> None:
        """Start the analytics module before frame processing loop begins."""
        if not self._is_initialized:
            raise RuntimeError(f"Cannot start AnalyticsModule '{self._name}': not initialized.")
        if self._is_running:
            return
        self.on_start()
        self._is_running = True
        logger.debug("AnalyticsModule '%s' started", self._name)

    @abstractmethod
    def update(self, context: AnalyticsContext) -> AnalyticsResult:
        """Process a single video frame iteration and return analytics results.

        Args:
            context: AnalyticsContext containing frame data, tracks, and zone results.

        Returns:
            AnalyticsResult instance.
        """
        pass

    def stop(self) -> None:
        """Stop the analytics module cleanly when execution completes."""
        if not self._is_running:
            return
        self.on_stop()
        self._is_running = False
        logger.debug("AnalyticsModule '%s' stopped", self._name)

    def dispose(self) -> None:
        """Release any internal resources allocated by the module."""
        if self._is_running:
            self.stop()
        self.on_dispose()
        self._is_initialized = False
        logger.debug("AnalyticsModule '%s' disposed", self._name)

    # --- Overridable Lifecycle Hooks ---

    def on_initialize(self, context: AnalyticsContext) -> None:
        """Hook called during module initialization."""
        pass

    def on_start(self) -> None:
        """Hook called when module starts."""
        pass

    def on_stop(self) -> None:
        """Hook called when module stops."""
        pass

    def on_dispose(self) -> None:
        """Hook called when module is disposed."""
        pass

    # --- Overridable Event Callbacks ---

    def on_frame_start(self, context: AnalyticsContext) -> None:
        """Callback invoked at the start of each frame iteration."""
        pass

    def on_frame_end(self, context: AnalyticsContext) -> None:
        """Callback invoked at the end of each frame iteration."""
        pass

    def on_track_created(self, track: Track) -> None:
        """Callback invoked when a new Track is created in TrackManager."""
        pass

    def on_track_updated(self, track: Track) -> None:
        """Callback invoked when a Track is updated with a new detection."""
        pass

    def on_track_confirmed(self, track: Track) -> None:
        """Callback invoked when a Track reaches CONFIRMED state."""
        pass

    def on_track_lost(self, track: Track) -> None:
        """Callback invoked when a Track transitions to LOST state."""
        pass

    def on_track_removed(self, track: Track) -> None:
        """Callback invoked when a Track is removed/archived from active tracks."""
        pass

    def on_zone_enter(self, event: ZoneEvent) -> None:
        """Callback invoked when a Track enters a spatial Zone."""
        pass

    def on_zone_exit(self, event: ZoneEvent) -> None:
        """Callback invoked when a Track exits a spatial Zone."""
        pass

    def on_zone_stay(self, event: ZoneEvent) -> None:
        """Callback invoked periodically while a Track remains inside a spatial Zone."""
        pass
