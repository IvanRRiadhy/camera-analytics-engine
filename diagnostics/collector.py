"""
Diagnostics Collector Component.

Provides DiagnosticsCollector class collecting frame execution latencies, per-plugin execution statistics,
and calculating RuntimeHealth status in a thread-safe, passive manner without performing logging.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Optional

from camera_analytics.diagnostics.metrics import (
    PluginMetrics,
    RuntimeHealth,
    RuntimeMetrics,
)


class DiagnosticsCollector:
    """Thread-safe passive collector aggregating frame metrics, plugin metrics, and RuntimeHealth."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._start_time: float = time.monotonic()
        self._total_frames: int = 0
        self._total_latency_ms: float = 0.0
        self._peak_latency_ms: float = 0.0
        self._dropped_frames: int = 0
        self._plugin_metrics: dict[str, PluginMetrics] = {}
        self._runtime_error_count: int = 0

    def record_frame(self, frame_latency_ms: float, dropped: bool = False) -> None:
        """Record frame execution latency and dropped frame status.

        Args:
            frame_latency_ms: Execution latency of the frame in milliseconds.
            dropped: Boolean flag indicating if frame was dropped.
        """
        with self._lock:
            self._total_frames += 1
            self._total_latency_ms += frame_latency_ms
            if frame_latency_ms > self._peak_latency_ms:
                self._peak_latency_ms = frame_latency_ms
            if dropped:
                self._dropped_frames += 1

    def record_plugin_execution(
        self,
        module_id: str,
        execution_time_ms: float,
        events_count: int = 0,
    ) -> None:
        """Record a successful module execution.

        Args:
            module_id: Unique string identifier of module.
            execution_time_ms: Execution duration in milliseconds.
            events_count: Number of analytics events generated.
        """
        with self._lock:
            pm = self._plugin_metrics.setdefault(module_id, PluginMetrics(module_id=module_id))
            pm.executed_count += 1
            pm.published_events += events_count

            # Update latency statistics
            if pm.executed_count == 1:
                pm.min_execution_time_ms = execution_time_ms
                pm.max_execution_time_ms = execution_time_ms
                pm.average_execution_time_ms = execution_time_ms
            else:
                if execution_time_ms < pm.min_execution_time_ms:
                    pm.min_execution_time_ms = execution_time_ms
                if execution_time_ms > pm.max_execution_time_ms:
                    pm.max_execution_time_ms = execution_time_ms
                # Cumulative moving average
                prev_total = pm.average_execution_time_ms * (pm.executed_count - 1)
                pm.average_execution_time_ms = (prev_total + execution_time_ms) / pm.executed_count

    def record_plugin_skip(self, module_id: str) -> None:
        """Record a module skip by ExecutionScheduler.

        Args:
            module_id: Unique string identifier of module.
        """
        with self._lock:
            pm = self._plugin_metrics.setdefault(module_id, PluginMetrics(module_id=module_id))
            pm.skipped_count += 1

    def record_plugin_error(self, module_id: str) -> None:
        """Record an exception isolated error for a module.

        Args:
            module_id: Unique string identifier of module.
        """
        with self._lock:
            pm = self._plugin_metrics.setdefault(module_id, PluginMetrics(module_id=module_id))
            pm.error_count += 1

    def record_runtime_error(self) -> None:
        """Record a general runtime kernel error."""
        with self._lock:
            self._runtime_error_count += 1

    def get_runtime_metrics(self) -> RuntimeMetrics:
        """Calculate and return snapshot of current RuntimeMetrics."""
        with self._lock:
            elapsed = time.monotonic() - self._start_time
            fps = self._total_frames / max(elapsed, 0.001)
            avg_lat = self._total_latency_ms / max(self._total_frames, 1)

            return RuntimeMetrics(
                total_frames=self._total_frames,
                fps=fps,
                average_latency_ms=avg_lat,
                peak_latency_ms=self._peak_latency_ms,
                dropped_frames=self._dropped_frames,
            )

    def get_plugin_metrics(self) -> list[PluginMetrics]:
        """Get copy of all recorded PluginMetrics."""
        with self._lock:
            return [
                PluginMetrics(
                    module_id=pm.module_id,
                    executed_count=pm.executed_count,
                    skipped_count=pm.skipped_count,
                    published_events=pm.published_events,
                    average_execution_time_ms=pm.average_execution_time_ms,
                    max_execution_time_ms=pm.max_execution_time_ms,
                    min_execution_time_ms=pm.min_execution_time_ms,
                    error_count=pm.error_count,
                )
                for pm in self._plugin_metrics.values()
            ]

    def evaluate_health(self) -> RuntimeHealth:
        """Evaluate current RuntimeHealth status based on error counts and performance.

        Returns:
            RuntimeHealth enum status.
        """
        with self._lock:
            total_plugin_errors = sum(pm.error_count for pm in self._plugin_metrics.values())

            if self._runtime_error_count > 5:
                return RuntimeHealth.FAILED

            if total_plugin_errors > 10:
                return RuntimeHealth.DEGRADED

            if total_plugin_errors > 0 or self._runtime_error_count > 0:
                return RuntimeHealth.WARNING

            return RuntimeHealth.HEALTHY
