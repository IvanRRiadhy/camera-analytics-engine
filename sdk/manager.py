"""
Analytics Manager and Lifecycle Coordinator.

Coordinates the complete lifecycle of all registered Analytics Modules, dispatches track
and spatial events, enforces Exception Isolation, and aggregates Analytics Results.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Optional, Sequence

from camera_analytics.sdk.models import (
    AggregatedAnalyticsResult,
    AnalyticsContext,
    AnalyticsResult,
)
from camera_analytics.sdk.module import AnalyticsModule
from camera_analytics.sdk.registry import AnalyticsRegistry

if TYPE_CHECKING:
    from camera_analytics.core.zone_engine import ZoneEngineResult
    from camera_analytics.models.track import Track

logger = logging.getLogger(__name__)


class AnalyticsManager:
    """Manager for loading, running, dispatching events to, and aggregating results from Analytics Modules.

    Enforces Exception Isolation: A failure in one Analytics Module will not stop other modules
    or crash the framework pipeline.
    """

    def __init__(self) -> None:
        self._modules: dict[str, AnalyticsModule] = {}
        self._is_initialized = False
        self._is_running = False

    @property
    def modules(self) -> dict[str, AnalyticsModule]:
        """Dictionary of currently loaded AnalyticsModule instances."""
        return self._modules

    @property
    def is_running(self) -> bool:
        """Whether the manager is running active modules."""
        return self._is_running

    def register_module(self, module: AnalyticsModule) -> None:
        """Register an instantiated AnalyticsModule directly with the manager.

        Args:
            module: AnalyticsModule instance.
        """
        if module.name in self._modules:
            logger.warning("AnalyticsManager: Overwriting registered module instance '%s'", module.name)
        self._modules[module.name] = module
        logger.info("AnalyticsManager: Registered active module '%s'", module.name)

    def load_from_registry(self, module_names: Sequence[str]) -> None:
        """Instantiate and load modules from `AnalyticsRegistry` by string name.

        Args:
            module_names: Sequence of registered module string identifiers.
        """
        for name in module_names:
            try:
                instance = AnalyticsRegistry.create(name)
                self.register_module(instance)
            except Exception as exc:
                logger.error("AnalyticsManager: Failed to load module '%s' from registry (%s)", name, exc)

    # --- Lifecycle Management ---

    def initialize(self, context: AnalyticsContext) -> None:
        """Initialize all registered analytics modules."""
        if self._is_initialized:
            return

        for name, module in list(self._modules.items()):
            try:
                module.initialize(context)
            except Exception as exc:
                logger.error("Exception Isolation: Failed to initialize module '%s' (%s)", name, exc)

        self._is_initialized = True
        logger.info("AnalyticsManager: Initialized %d module(s)", len(self._modules))

    def start(self) -> None:
        """Start all initialized analytics modules."""
        if self._is_running:
            return

        for name, module in list(self._modules.items()):
            try:
                module.start()
            except Exception as exc:
                logger.error("Exception Isolation: Failed to start module '%s' (%s)", name, exc)

        self._is_running = True
        logger.info("AnalyticsManager: Started %d module(s)", len(self._modules))

    def process(
        self,
        context: AnalyticsContext,
        tracks_created: Optional[Sequence[Track]] = None,
        tracks_updated: Optional[Sequence[Track]] = None,
        tracks_confirmed: Optional[Sequence[Track]] = None,
        tracks_lost: Optional[Sequence[Track]] = None,
        tracks_removed: Optional[Sequence[Track]] = None,
    ) -> AggregatedAnalyticsResult:
        """Execute a single update iteration across all active Analytics Modules.

        Dispatches frame hooks, track callbacks, and spatial zone events with strict Exception Isolation,
        aggregating individual results into an `AggregatedAnalyticsResult`.

        Args:
            context: AnalyticsContext for the current frame iteration.
            tracks_created: Sequence of newly created Track objects.
            tracks_updated: Sequence of updated Track objects.
            tracks_confirmed: Sequence of newly confirmed Track objects.
            tracks_lost: Sequence of newly lost Track objects.
            tracks_removed: Sequence of removed/archived Track objects.

        Returns:
            AggregatedAnalyticsResult containing aggregated events, metrics, and error logs.
        """
        aggregated = AggregatedAnalyticsResult(
            frame_index=context.frame_index,
            timestamp=context.timestamp,
        )

        t0_total = time.monotonic()

        # 1. Dispatch Frame Start & Track Lifecycle Callbacks
        for name, module in self._modules.items():
            if not module.is_running:
                continue

            try:
                module.on_frame_start(context)

                if tracks_created:
                    for trk in tracks_created:
                        module.on_track_created(trk)
                if tracks_updated:
                    for trk in tracks_updated:
                        module.on_track_updated(trk)
                if tracks_confirmed:
                    for trk in tracks_confirmed:
                        module.on_track_confirmed(trk)
                if tracks_lost:
                    for trk in tracks_lost:
                        module.on_track_lost(trk)
                if tracks_removed:
                    for trk in tracks_removed:
                        module.on_track_removed(trk)
            except Exception as exc:
                err_msg = f"Module '{name}' callback error: {exc}"
                logger.error("Exception Isolation: %s", err_msg)
                aggregated.errors.append(err_msg)

        # 2. Dispatch ZoneEngine Spatial Events
        if context.zone_result and context.zone_result.events:
            for event in context.zone_result.events:
                for name, module in self._modules.items():
                    if not module.is_running:
                        continue
                    try:
                        from camera_analytics.core.zone_engine import ZoneEventType
                        if event.event_type == ZoneEventType.ENTER:
                            module.on_zone_enter(event)
                        elif event.event_type == ZoneEventType.EXIT:
                            module.on_zone_exit(event)
                        elif event.event_type == ZoneEventType.STAY:
                            module.on_zone_stay(event)
                    except Exception as exc:
                        err_msg = f"Module '{name}' zone event error: {exc}"
                        logger.error("Exception Isolation: %s", err_msg)
                        aggregated.errors.append(err_msg)

        # 3. Execute Module `update()` method & Collect Results
        for name, module in self._modules.items():
            if not module.is_running:
                continue

            t0_mod = time.monotonic()
            try:
                res = module.update(context)
                t1_mod = time.monotonic()
                if res is not None:
                    res.execution_time_ms = (t1_mod - t0_mod) * 1000.0
                    aggregated.results[name] = res
                    aggregated.all_events.extend(res.events)
                    aggregated.summary_metrics.update(res.metrics)
            except Exception as exc:
                err_msg = f"Module '{name}' update failed: {exc}"
                logger.error("Exception Isolation: %s", err_msg)
                aggregated.errors.append(err_msg)

            # Frame End Hook
            try:
                module.on_frame_end(context)
            except Exception as exc:
                err_msg = f"Module '{name}' frame end error: {exc}"
                logger.error("Exception Isolation: %s", err_msg)
                aggregated.errors.append(err_msg)

        t1_total = time.monotonic()
        aggregated.total_execution_time_ms = (t1_total - t0_total) * 1000.0

        return aggregated

    def stop(self) -> None:
        """Stop all active analytics modules."""
        for name, module in list(self._modules.items()):
            try:
                module.stop()
            except Exception as exc:
                logger.error("Exception Isolation: Failed to stop module '%s' (%s)", name, exc)

        self._is_running = False
        logger.info("AnalyticsManager: Stopped all modules")

    def dispose(self) -> None:
        """Dispose all registered analytics modules."""
        if self._is_running:
            self.stop()

        for name, module in list(self._modules.items()):
            try:
                module.dispose()
            except Exception as exc:
                logger.error("Exception Isolation: Failed to dispose module '%s' (%s)", name, exc)

        self._modules.clear()
        self._is_initialized = False
        logger.info("AnalyticsManager: Disposed all modules")
