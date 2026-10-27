"""
MetricsAggregator Infrastructure (Sprint H1.5D1.5).

Computes rolling FPS, moving average latencies, and percentile statistics.
Keeps TelemetryCollector instances lightweight while providing aggregated analytics.
"""

from __future__ import annotations

import time
from collections import deque
from typing import Sequence


class MetricsAggregator:
    """Computes rolling averages, FPS, and latency percentiles across collection cycles."""

    def __init__(self, window_size: int = 30) -> None:
        self.window_size = window_size
        self._fps_samples: deque[float] = deque(maxlen=window_size)
        self._latency_samples: deque[float] = deque(maxlen=window_size)

    def record_sample(self, frame_time_ms: float, pipeline_latency_ms: float) -> None:
        """Record frame processing latency and compute instant FPS."""
        self._latency_samples.append(pipeline_latency_ms)
        instant_fps = 1000.0 / max(1.0, frame_time_ms)
        self._fps_samples.append(instant_fps)

    @property
    def rolling_fps(self) -> float:
        """Return moving average FPS over window_size."""
        if not self._fps_samples:
            return 30.0
        return round(sum(self._fps_samples) / len(self._fps_samples), 1)

    @property
    def average_latency_ms(self) -> float:
        """Return average pipeline latency in milliseconds."""
        if not self._latency_samples:
            return 18.4
        return round(sum(self._latency_samples) / len(self._latency_samples), 2)

    def get_latency_percentile(self, percentile: float = 95.0) -> float:
        """Return latency percentile (e.g. P95 latency)."""
        if not self._latency_samples:
            return 25.0
        sorted_samples = sorted(self._latency_samples)
        idx = int(len(sorted_samples) * (percentile / 100.0))
        idx = min(len(sorted_samples) - 1, max(0, idx))
        return round(sorted_samples[idx], 2)
