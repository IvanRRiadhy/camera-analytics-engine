"""
Telemetry Interfaces.

Defines abstract base contracts for metrics collection, accumulation,
and telemetry provider instances in accordance with enterprise guidelines.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional


class IMetricsAccumulator(ABC):
    """Abstract contract for numerical metric accumulators."""

    @abstractmethod
    def add(self, value: float) -> None:
        """Record a single numerical metric sample."""

    @abstractmethod
    def get_average(self) -> float:
        """Calculate arithmetic mean of samples in the current window."""

    @abstractmethod
    def reset(self) -> None:
        """Reset internal sample buffer."""


class IMetricsCollector(ABC):
    """Abstract contract for pipeline runtime metrics collection."""

    @abstractmethod
    def record_reader_fps(self, pipeline_id: str, fps: float) -> None:
        """Record RTSP frame ingestion FPS."""

    @abstractmethod
    def record_execution_fps(self, pipeline_id: str, fps: float) -> None:
        """Record AI execution FPS."""

    @abstractmethod
    def record_pipeline_latency(self, pipeline_id: str, latency_ms: float) -> None:
        """Record total frame pipeline latency in milliseconds."""

    @abstractmethod
    def record_counts(self, pipeline_id: str, detections_count: int, tracks_count: int) -> None:
        """Record active detection and track counts for a frame."""

    @abstractmethod
    def get_metrics(self, pipeline_id: str) -> Optional[Any]:
        """Retrieve aggregated metrics snapshot for a pipeline."""
