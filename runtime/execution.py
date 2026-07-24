"""
Execution Engine Component.

Executes active Analytics Modules on incoming immutable Scene snapshots with Exception Isolation,
ExecutionScheduler timing control, and DiagnosticsCollector profiling.
Guarantees that a crash in one analytics module will not crash the Analytics Runtime Kernel or other modules.
Tracks execution statistics and maintains deterministic execution order.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Optional

from camera_analytics.diagnostics.collector import DiagnosticsCollector
from camera_analytics.runtime.context import RuntimeContext
from camera_analytics.runtime.lifecycle import LifecycleManager, ModuleState
from camera_analytics.scheduler.core import ExecutionScheduler
from camera_analytics.sdk import AggregatedAnalyticsResult, AnalyticsResult

if TYPE_CHECKING:
    from camera_analytics.scene.models import Scene

logger = logging.getLogger(__name__)


class ExecutionEngine:
    """Engine responsible for dispatching Immutable Scene snapshots to active Analytics Modules with Exception Isolation, ExecutionScheduler, and DiagnosticsCollector."""

    def __init__(
        self,
        lifecycle_manager: LifecycleManager,
        runtime_context: Optional[RuntimeContext] = None,
        scheduler: Optional[ExecutionScheduler] = None,
        diagnostics_collector: Optional[DiagnosticsCollector] = None,
    ) -> None:
        self._lifecycle_manager = lifecycle_manager
        self._context = runtime_context or RuntimeContext()
        self._scheduler = scheduler or ExecutionScheduler()
        self._diagnostics = diagnostics_collector or DiagnosticsCollector()

    @property
    def scheduler(self) -> ExecutionScheduler:
        """Reference to ExecutionScheduler."""
        return self._scheduler

    @property
    def diagnostics(self) -> DiagnosticsCollector:
        """Reference to DiagnosticsCollector."""
        return self._diagnostics

    def execute_scene(self, scene: Scene) -> AggregatedAnalyticsResult:
        """Dispatch immutable Scene snapshot to enabled RUNNING Analytics Modules according to ExecutionScheduler timing rules.

        Args:
            scene: Immutable Scene domain snapshot.

        Returns:
            AggregatedAnalyticsResult containing all collected events, payloads, and errors.
        """
        t0 = time.perf_counter()
        aggregated = AggregatedAnalyticsResult(
            frame_index=scene.frame.frame_index,
            timestamp=scene.frame.timestamp,
        )

        # Retrieve registered active modules in priority order
        active_pairs = [
            (rec.descriptor, rec.module)
            for name, rec in self._lifecycle_manager._records.items()
            if rec.state == ModuleState.RUNNING and rec.descriptor.enabled
        ]
        active_pairs.sort(key=lambda pair: pair[0].priority)

        executed_modules: list[str] = []
        skipped_modules: list[str] = []
        error_modules: list[str] = []

        for desc, module in active_pairs:
            name = desc.module_id

            # 1. Evaluate ExecutionScheduler timing rule
            if not self._scheduler.should_execute(desc, scene.frame.frame_index):
                skipped_modules.append(name)
                self._diagnostics.record_plugin_skip(name)
                continue

            try:
                mod_t0 = time.perf_counter()

                # Dispatch immutable Scene snapshot to Analytics Module
                if hasattr(module, "process_scene") and callable(getattr(module, "process_scene")):
                    result = module.process_scene(scene)
                elif hasattr(module, "process") and callable(getattr(module, "process")):
                    result = module.process(scene)
                elif hasattr(module, "update") and callable(getattr(module, "update")):
                    from camera_analytics.sdk.models import AnalyticsContext
                    sdk_ctx = AnalyticsContext(
                        frame_context=None,
                        runtime_state=None,
                        track_manager=None,
                        active_tracks=list(scene.tracks),  # type: ignore
                        zones=list(scene.zones),  # type: ignore
                        zone_result=None,
                        frame_index=scene.frame.frame_index,
                        timestamp=scene.frame.timestamp,
                    )
                    result = module.update(sdk_ctx)
                else:
                    result = AnalyticsResult(module_name=name)

                mod_t1 = time.perf_counter()
                mod_duration_ms = (mod_t1 - mod_t0) * 1000.0

                events_cnt = 0
                if result:
                    result.execution_time_ms = mod_duration_ms
                    aggregated.results[name] = result
                    if result.events:
                        events_cnt = len(result.events)
                        aggregated.all_events.extend(result.events)

                executed_modules.append(name)

                # Record passive module execution metrics
                self._diagnostics.record_plugin_execution(
                    module_id=name,
                    execution_time_ms=mod_duration_ms,
                    events_count=events_cnt,
                )

            except Exception as exc:
                # Exception Isolation: Capture error safely without crashing execution engine
                err_msg = f"Execution error in module '{name}': {exc}"
                logger.error("Exception Isolation Barrier: %s", err_msg)

                # Record error in module lifecycle record & diagnostics
                rec = self._lifecycle_manager._records.get(name)
                if rec:
                    rec.error_count += 1
                    rec.last_error = str(exc)

                error_modules.append(name)
                aggregated.errors.append(err_msg)
                self._diagnostics.record_plugin_error(name)

        t1 = time.perf_counter()
        total_duration_ms = (t1 - t0) * 1000.0
        aggregated.total_execution_time_ms = total_duration_ms

        # Record passive frame metrics
        self._diagnostics.record_frame(total_duration_ms)

        # Record runtime statistics into RuntimeContext
        self._context.statistics.record_scene_execution(
            execution_time_ms=total_duration_ms,
            events_count=len(aggregated.all_events),
            executed_modules=executed_modules,
            error_modules=error_modules,
        )

        return aggregated
