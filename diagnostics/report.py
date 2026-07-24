"""
Diagnostics Report Component.

Provides DiagnosticsReport dataclass summarizing Runtime Summary, Plugin Execution Summaries,
Slowest Plugin, Fastest Plugin, Highest Event Producer, Highest Skip Ratio, and Runtime Health.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from camera_analytics.diagnostics.collector import DiagnosticsCollector
from camera_analytics.diagnostics.metrics import (
    PluginMetrics,
    RuntimeHealth,
    RuntimeMetrics,
)


@dataclass(slots=True)
class DiagnosticsReport:
    """Comprehensive diagnostic report for Analytics Runtime performance and health.

    Attributes:
        runtime_metrics: Overall RuntimeMetrics container.
        health: Current RuntimeHealth status enum.
        plugin_metrics: List of PluginMetrics for registered modules.
        slowest_plugin: PluginMetrics of the slowest module (by peak execution time).
        fastest_plugin: PluginMetrics of the fastest module (by avg execution time).
        highest_event_producer: PluginMetrics of module producing most events.
        highest_skip_ratio_plugin: PluginMetrics of module skipped most frequently.
    """

    runtime_metrics: RuntimeMetrics = field(default_factory=RuntimeMetrics)
    health: RuntimeHealth = RuntimeHealth.HEALTHY
    plugin_metrics: list[PluginMetrics] = field(default_factory=list)
    slowest_plugin: Optional[PluginMetrics] = None
    fastest_plugin: Optional[PluginMetrics] = None
    highest_event_producer: Optional[PluginMetrics] = None
    highest_skip_ratio_plugin: Optional[PluginMetrics] = None

    @classmethod
    def generate(cls, collector: DiagnosticsCollector) -> DiagnosticsReport:
        """Generate a DiagnosticsReport snapshot from a DiagnosticsCollector instance.

        Args:
            collector: DiagnosticsCollector instance.

        Returns:
            DiagnosticsReport object containing calculated breakdowns.
        """
        rt_metrics = collector.get_runtime_metrics()
        health_status = collector.evaluate_health()
        plugins = collector.get_plugin_metrics()

        slowest: Optional[PluginMetrics] = None
        fastest: Optional[PluginMetrics] = None
        top_events: Optional[PluginMetrics] = None
        top_skips: Optional[PluginMetrics] = None

        executed_plugins = [p for p in plugins if p.executed_count > 0]

        if executed_plugins:
            slowest = max(executed_plugins, key=lambda p: p.max_execution_time_ms)
            fastest = min(executed_plugins, key=lambda p: p.average_execution_time_ms)
            top_events = max(plugins, key=lambda p: p.published_events)
            top_skips = max(plugins, key=lambda p: p.skip_ratio)

        return cls(
            runtime_metrics=rt_metrics,
            health=health_status,
            plugin_metrics=plugins,
            slowest_plugin=slowest,
            fastest_plugin=fastest,
            highest_event_producer=top_events,
            highest_skip_ratio_plugin=top_skips,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert diagnostic report to summary dictionary."""
        return {
            "runtime_health": self.health.name,
            "runtime_metrics": self.runtime_metrics.to_dict(),
            "plugin_count": len(self.plugin_metrics),
            "slowest_plugin": self.slowest_plugin.module_id if self.slowest_plugin else None,
            "fastest_plugin": self.fastest_plugin.module_id if self.fastest_plugin else None,
            "highest_event_producer": self.highest_event_producer.module_id if self.highest_event_producer else None,
            "highest_skip_ratio_plugin": self.highest_skip_ratio_plugin.module_id if self.highest_skip_ratio_plugin else None,
            "plugins": [p.to_dict() for p in self.plugin_metrics],
        }
