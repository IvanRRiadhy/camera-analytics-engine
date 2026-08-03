"""
Runtime Diagnostics & Profiling Package.

Provides RuntimeHealth, RuntimeMetrics, PluginMetrics, DiagnosticsCollector,
HardwareDiagnosticCollector, and DiagnosticsReport for inspecting platform latency, module execution performance, and health status.
"""

from camera_analytics.diagnostics.collector import (
    DiagnosticsCollector,
    HardwareDiagnosticCollector,
)
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
    "HardwareDiagnosticCollector",
    "DiagnosticsReport",
]
