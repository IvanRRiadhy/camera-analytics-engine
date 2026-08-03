"""
Diagnostics Collector Component.

Provides DiagnosticsCollector class collecting frame execution latencies, per-plugin execution statistics,
RuntimeHealth status, and HardwareDiagnosticCollector for real-time CPU/GPU system metrics.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Optional

import psutil
import torch

from camera_analytics.diagnostics.metrics import (
    PluginMetrics,
    RuntimeHealth,
    RuntimeMetrics,
)

logger = logging.getLogger(__name__)


class HardwareDiagnosticCollector:
    """Thread-safe hardware resource metrics collector querying CPU, RAM, CUDA, and NVML GPU stats."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._has_nvml = False
        try:
            import pynvml
            pynvml.nvmlInit()
            self._pynvml = pynvml
            self._has_nvml = True
        except Exception:
            self._has_nvml = False

    def collect_system_metrics(self) -> dict[str, Any]:
        """Collect current system CPU, RAM, and GPU hardware metrics.

        Returns:
            Dict containing cpu_usage_percent, memory_used_mb, memory_total_mb,
            and gpu_metrics (gpu_usage_percent, vram_used_mb, vram_total_mb,
            gpu_temperature_c, power_draw_watts).
        """
        with self._lock:
            cpu_pct = psutil.cpu_percent(interval=None)
            mem = psutil.virtual_memory()

            gpu_metrics = {
                "gpu_usage_percent": 0.0,
                "vram_used_mb": 0,
                "vram_total_mb": 0,
                "gpu_temperature_c": 0.0,
                "power_draw_watts": 0.0,
            }

            if torch.cuda.is_available():
                try:
                    device_id = 0
                    vram_alloc = torch.cuda.memory_allocated(device_id) // (1024 * 1024)
                    vram_total = torch.cuda.get_device_properties(device_id).total_memory // (1024 * 1024)
                    gpu_metrics["vram_used_mb"] = vram_alloc
                    gpu_metrics["vram_total_mb"] = vram_total
                except Exception:
                    pass

                if self._has_nvml:
                    try:
                        handle = self._pynvml.nvmlDeviceGetHandleByIndex(0)
                        util = self._pynvml.nvmlDeviceGetUtilizationRates(handle)
                        temp = self._pynvml.nvmlDeviceGetTemperature(handle, self._pynvml.NVML_TEMPERATURE_GPU)
                        power = self._pynvml.nvmlDeviceGetPowerUsage(handle) / 1000.0

                        gpu_metrics["gpu_usage_percent"] = float(util.gpu)
                        gpu_metrics["gpu_temperature_c"] = float(temp)
                        gpu_metrics["power_draw_watts"] = float(power)
                    except Exception:
                        pass

            return {
                "cpu_usage_percent": float(cpu_pct),
                "memory_used_mb": mem.used // (1024 * 1024),
                "memory_total_mb": mem.total // (1024 * 1024),
                "gpu_metrics": gpu_metrics,
            }


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
        """Record frame execution latency and dropped frame status."""
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
        """Record a successful module execution."""
        with self._lock:
            pm = self._plugin_metrics.setdefault(module_id, PluginMetrics(module_id=module_id))
            pm.executed_count += 1
            pm.published_events += events_count

            if pm.executed_count == 1:
                pm.min_execution_time_ms = execution_time_ms
                pm.max_execution_time_ms = execution_time_ms
                pm.average_execution_time_ms = execution_time_ms
            else:
                if execution_time_ms < pm.min_execution_time_ms:
                    pm.min_execution_time_ms = execution_time_ms
                if execution_time_ms > pm.max_execution_time_ms:
                    pm.max_execution_time_ms = execution_time_ms
                prev_total = pm.average_execution_time_ms * (pm.executed_count - 1)
                pm.average_execution_time_ms = (prev_total + execution_time_ms) / pm.executed_count

    def record_plugin_skip(self, module_id: str) -> None:
        """Record a module skip by ExecutionScheduler."""
        with self._lock:
            pm = self._plugin_metrics.setdefault(module_id, PluginMetrics(module_id=module_id))
            pm.skipped_count += 1

    def record_plugin_error(self, module_id: str) -> None:
        """Record an exception isolated error for a module."""
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
        """Evaluate current RuntimeHealth status based on error counts and performance."""
        with self._lock:
            total_plugin_errors = sum(pm.error_count for pm in self._plugin_metrics.values())

            if self._runtime_error_count > 5:
                return RuntimeHealth.FAILED

            if total_plugin_errors > 10:
                return RuntimeHealth.DEGRADED

            if total_plugin_errors > 0 or self._runtime_error_count > 0:
                return RuntimeHealth.WARNING

            return RuntimeHealth.HEALTHY
