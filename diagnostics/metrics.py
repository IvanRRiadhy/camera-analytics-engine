"""
Diagnostics Metrics Component.

Provides RuntimeHealth enum, RuntimeMetrics dataclass, and PluginMetrics dataclass
representing real-time performance, execution latency, and health statistics for Analytics Modules and Runtime Kernel.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List


class RuntimeHealth(Enum):
    """Health status enumeration for the Analytics Runtime Kernel."""

    HEALTHY = auto()
    WARNING = auto()
    DEGRADED = auto()
    FAILED = auto()


@dataclass(slots=True)
class RuntimeMetrics:
    """Real-time latency and frame execution metrics for Analytics Runtime Kernel.

    Attributes:
        total_frames: Total number of frames processed.
        fps: Current processing frame rate (frames per second).
        average_latency_ms: Average frame processing latency in milliseconds.
        peak_latency_ms: Maximum frame processing latency in milliseconds.
        dropped_frames: Count of dropped or skipped frames.
    """

    total_frames: int = 0
    fps: float = 0.0
    average_latency_ms: float = 0.0
    peak_latency_ms: float = 0.0
    dropped_frames: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics summary to dictionary."""
        return {
            "total_frames": self.total_frames,
            "fps": round(self.fps, 2),
            "average_latency_ms": round(self.average_latency_ms, 3),
            "peak_latency_ms": round(self.peak_latency_ms, 3),
            "dropped_frames": self.dropped_frames,
        }


@dataclass(slots=True)
class PluginMetrics:
    """Execution statistics and performance metrics for a specific Analytics Module.

    Attributes:
        module_id: Unique string identifier of the module.
        executed_count: Total number of frames on which the module executed.
        skipped_count: Total number of frames on which the module was skipped by scheduler.
        published_events: Total number of analytics events published by the module.
        average_execution_time_ms: Average execution duration in milliseconds.
        max_execution_time_ms: Peak execution duration in milliseconds.
        min_execution_time_ms: Minimum execution duration in milliseconds.
        error_count: Total count of exceptions caught by Exception Isolation.
    """

    module_id: str
    executed_count: int = 0
    skipped_count: int = 0
    published_events: int = 0
    average_execution_time_ms: float = 0.0
    max_execution_time_ms: float = 0.0
    min_execution_time_ms: float = 0.0
    error_count: int = 0

    @property
    def total_evaluations(self) -> int:
        """Total frame scheduling evaluations."""
        return self.executed_count + self.skipped_count

    @property
    def skip_ratio(self) -> float:
        """Ratio of skipped evaluations to total evaluations."""
        if self.total_evaluations == 0:
            return 0.0
        return self.skipped_count / self.total_evaluations

    def to_dict(self) -> dict[str, Any]:
        """Convert plugin metrics summary to dictionary."""
        return {
            "module_id": self.module_id,
            "executed_count": self.executed_count,
            "skipped_count": self.skipped_count,
            "published_events": self.published_events,
            "average_execution_time_ms": round(self.average_execution_time_ms, 3),
            "max_execution_time_ms": round(self.max_execution_time_ms, 3),
            "min_execution_time_ms": round(self.min_execution_time_ms, 3),
            "error_count": self.error_count,
            "skip_ratio": round(self.skip_ratio, 4),
        }
