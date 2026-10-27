"""
Inference Profiler Infrastructure (Sprint H1.4.7).

Provides reusable, model-agnostic operational telemetry profiling across modules:
tracks execution count, skipped count, latency distributions (average, median, P95, P99),
queue waiting time, dropped requests, timeouts, quality rejections, and GPU/CPU utilization.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Sequence
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ModuleProfileMetrics:
    """Detailed operational performance metrics for an AI module."""

    module_id: str
    execution_count: int = 0
    skipped_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    quality_rejected_count: int = 0
    cooldown_skipped_count: int = 0
    frame_stride_skipped_count: int = 0
    dropped_requests_count: int = 0
    timeout_count: int = 0
    total_runtime_ms: float = 0.0
    last_latency_ms: float = 0.0
    queue_wait_time_ms: float = 0.0
    gpu_memory_mb: float = 0.0
    cpu_usage_pct: float = 0.0
    latency_history: list[float] = field(default_factory=list)

    @property
    def average_latency_ms(self) -> float:
        """Average execution latency in milliseconds."""
        return round(float(np.mean(self.latency_history)), 3) if self.latency_history else 0.0

    @property
    def median_latency_ms(self) -> float:
        """Median (P50) execution latency in milliseconds."""
        return round(float(np.median(self.latency_history)), 3) if self.latency_history else 0.0

    @property
    def p95_latency_ms(self) -> float:
        """P95 execution latency in milliseconds."""
        return round(float(np.percentile(self.latency_history, 95)), 3) if self.latency_history else 0.0

    @property
    def p99_latency_ms(self) -> float:
        """P99 execution latency in milliseconds."""
        return round(float(np.percentile(self.latency_history, 99)), 3) if self.latency_history else 0.0

    def record_execution(self, latency_ms: float, batch_size: int = 1, success: bool = True, wait_time_ms: float = 0.0) -> None:
        """Record an execution run."""
        self.execution_count += batch_size
        if success:
            self.success_count += batch_size
        else:
            self.failure_count += batch_size

        self.total_runtime_ms += latency_ms
        self.last_latency_ms = round(latency_ms, 3)
        self.queue_wait_time_ms = round(wait_time_ms, 3)
        self.latency_history.append(latency_ms)
        if len(self.latency_history) > 1000:
            self.latency_history.pop(0)

    def to_dict(self) -> dict[str, Any]:
        """Serialize metrics snapshot into dictionary format."""
        return {
            "moduleId": self.module_id,
            "executionCount": self.execution_count,
            "skippedCount": self.skipped_count,
            "successCount": self.success_count,
            "failureCount": self.failure_count,
            "qualityRejectedCount": self.quality_rejected_count,
            "cooldownSkippedCount": self.cooldown_skipped_count,
            "frameStrideSkippedCount": self.frame_stride_skipped_count,
            "droppedRequestsCount": self.dropped_requests_count,
            "timeoutCount": self.timeout_count,
            "averageLatencyMs": self.average_latency_ms,
            "medianLatencyMs": self.median_latency_ms,
            "p95LatencyMs": self.p95_latency_ms,
            "p99LatencyMs": self.p99_latency_ms,
            "lastLatencyMs": self.last_latency_ms,
            "totalRuntimeMs": round(self.total_runtime_ms, 3),
            "queueWaitTimeMs": self.queue_wait_time_ms,
            "gpuMemoryMb": round(self.gpu_memory_mb, 1),
            "cpuUsagePct": round(self.cpu_usage_pct, 1),
        }


class InferenceProfiler:
    """Centralized reusable profiler tracking telemetry for all Human Analytics modules."""

    def __init__(self) -> None:
        self._profiles: dict[str, ModuleProfileMetrics] = {}

    def get_profile(self, module_id: str) -> ModuleProfileMetrics:
        """Retrieve or instantiate profile metrics container for a module."""
        if module_id not in self._profiles:
            self._profiles[module_id] = ModuleProfileMetrics(module_id=module_id)
        return self._profiles[module_id]

    def record_quality_rejection(self, module_id: str, count: int = 1) -> None:
        """Record quality rejection event."""
        p = self.get_profile(module_id)
        p.quality_rejected_count += count
        p.skipped_count += count

    def record_stride_skip(self, module_id: str, count: int = 1) -> None:
        """Record frame stride skip event."""
        p = self.get_profile(module_id)
        p.frame_stride_skipped_count += count
        p.skipped_count += count

    def record_cooldown_skip(self, module_id: str, count: int = 1) -> None:
        """Record cooldown skip event."""
        p = self.get_profile(module_id)
        p.cooldown_skipped_count += count
        p.skipped_count += count

    def record_dropped_request(self, module_id: str, count: int = 1) -> None:
        """Record dropped request event."""
        p = self.get_profile(module_id)
        p.dropped_requests_count += count

    def get_all_profiles(self) -> dict[str, dict[str, Any]]:
        """Return serialized metrics dictionary for all tracked modules."""
        return {m_id: p.to_dict() for m_id, p in self._profiles.items()}
