"""
Plugin Manager orchestrating dynamic loading, lifecycle, and error isolation.
"""

from __future__ import annotations

import logging
import time
import traceback
from typing import Any, Optional

from camera_analytics.plugins.framework.context import PluginContext
from camera_analytics.plugins.framework.loader import PluginLoader
from camera_analytics.plugins.framework.registry import PluginRegistry
from camera_analytics.plugins.framework.states import PluginState
from camera_analytics.sdk.base_plugin import BaseAnalyticsPlugin

logger = logging.getLogger(__name__)


class PluginManager:
    """Enterprise Manager providing lifecycle orchestration and exception isolation for vision plugins."""

    def __init__(self, pipeline_id: str = "pipeline_default") -> None:
        self.pipeline_id = pipeline_id
        self.registry = PluginRegistry()
        self.loader = PluginLoader()

    def load_plugin(self, entry_point: str, name: str, context: PluginContext) -> Optional[BaseAnalyticsPlugin]:
        """Dynamically load, instantiate, initialize, and warmup a vision plugin.

        Startup Sequence:
            Bootstrap -> PluginManager -> PluginLoader -> Instantiate -> Initialize -> Warmup -> Running
        """
        logger.info("[PluginManager] Orchestrating startup sequence for plugin '%s' (EntryPoint: %s)...", name, entry_point)

        try:
            # 1. Instantiate via Loader
            plugin = self.loader.instantiate_plugin(entry_point=entry_point, name=name)
            plugin.state = PluginState.LOADED

            # 2. Initialize with injected Context
            if plugin.initialize(context):
                plugin.state = PluginState.INITIALIZED

            # 3. Warmup
            if plugin.warmup():
                plugin.state = PluginState.WARMUP

            # 4. Start execution state
            plugin.start() # Transitions to PluginState.RUNNING

            # 5. Register in Registry
            self.registry.register(plugin)
            logger.info("[PluginManager] Loaded Plugin '%s' -> State: %s", plugin.name, plugin.state.name)
            return plugin

        except Exception as exc:
            logger.error("[PluginManager] Failed to load plugin '%s': %s\n%s", name, exc, traceback.format_exc())
            return None

    def process(self, context: Any) -> list[Any]:
        """Execute frame inference across all running plugins using pre-computed SharedAnalyticsContext with exception isolation.

        If a plugin fails, its state is marked as FAILED without stopping the pipeline or other plugins.
        """
        start_t = time.perf_counter()
        events: list[Any] = []
        plugins = self.registry.get_all_plugins()

        for plugin in plugins:
            if plugin.state != PluginState.RUNNING:
                continue

            try:
                # Execute plugin with SharedAnalyticsContext
                if hasattr(plugin, "process"):
                    results = plugin.process(context)
                else:
                    results = plugin.process_frame(getattr(context, "frame", None), getattr(context, "metadata", None))

                if results:
                    events.extend(results)
                    plugin.events_generated += len(results)
                plugin.frames_processed += 1

            except Exception as exc:
                plugin.errors += 1
                plugin.state = PluginState.FAILED
                logger.error(
                    "[PluginManager] Exception isolated in plugin '%s'. Marked state as FAILED: %s",
                    plugin.name,
                    exc,
                )

        if hasattr(context, "stage_timings_ms"):
            context.stage_timings_ms["plugin_execution_time_ms"] = round((time.perf_counter() - start_t) * 1000.0, 2)

        return events

    def process_frame(self, frame: Any, metadata: Optional[dict[str, Any]] = None) -> list[Any]:
        """Backwards compatibility process_frame method wrapping process(context)."""
        from camera_analytics.context.unified_context import SharedAnalyticsContext
        ctx = SharedAnalyticsContext(frame=frame, metadata=metadata or {})
        return self.process(ctx)

    def start_all(self) -> None:
        """Start all registered plugins."""
        for plugin in self.registry.get_all_plugins():
            if plugin.state != PluginState.RUNNING:
                plugin.start()

    def stop_all(self) -> None:
        """Stop all registered plugins."""
        for plugin in self.registry.get_all_plugins():
            plugin.shutdown()

    def get_plugin_runtimes(self) -> list[dict[str, Any]]:
        """Get telemetry export snapshot for all managed plugins."""
        snapshots: list[dict[str, Any]] = []
        for p in self.registry.get_all_plugins():
            snapshots.append({
                "plugin_name": p.name,
                "version": p.version,
                "status": p.state.name,
                "frames_processed": p.frames_processed,
                "events_generated": p.events_generated,
                "errors": p.errors,
                "warnings": p.warnings,
                "last_inference_time_ms": p.last_inference_time_ms
            })
        return snapshots
