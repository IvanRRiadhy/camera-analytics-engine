"""
Runtime Diagnostics & Profiling Package.

Provides RuntimeHealth, RuntimeMetrics, PluginMetrics, DiagnosticsCollector,
and DiagnosticsReport for inspecting platform latency, module execution performance, and health status.
"""

from camera_analytics.diagnostics.collector import DiagnosticsCollector
from camera_analytics.diagnostics.metrics import (
    PluginMetrics,
    RuntimeHealth,
    RuntimeMetrics,
)
from camera_analytics.diagnostics.report import DiagnosticsReport

__all__ = [
    "RuntimeHealth",
    "RuntimeMetrics",
    "PluginMetrics",
    "DiagnosticsCollector",
    "DiagnosticsReport",
]
