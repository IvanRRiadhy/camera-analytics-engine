"""
Telemetry Accumulator Component.

Provides thread-safe, instance-isolated metric accumulators producing immutable
PipelineMetrics snapshots per camera pipeline.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Optional

from camera_analytics.telemetry.interfaces import IMetricsAccumulator
from camera_analytics.telemetry.models import PipelineMetrics


class RollingMetricsAccumulator(IMetricsAccumulator):
    """Thread-safe rolling window average accumulator for latency and throughput metrics.

    Args:
        capacity: Maximum sample window size.
    """

    def __init__(self, capacity: int = 100) -> None:
        self._capacity = max(1, capacity)
        self._samples: deque[float] = deque(maxlen=self._capacity)
        self._lock = threading.Lock()

    def add(self, value: float) -> None:
        """Add a sample to the rolling window.

        Args:
            value: Numerical metric sample value.
        """
        with self._lock:
            self._samples.append(float(value))

    def get_average(self) -> float:
        """Calculate mean value of samples in current window.

        Returns:
            Arithmetic average float value, or 0.0 if empty.
        """
        with self._lock:
            if not self._samples:
                return 0.0
            return sum(self._samples) / len(self._samples)

    def reset(self) -> None:
        """Clear all buffered metric samples."""
        with self._lock:
            self._samples.clear()

    def count(self) -> int:
        """Number of samples currently buffered."""
        with self._lock:
            return len(self._samples)


class PipelineMetricsAccumulator:
    """Thread-safe metric accumulator owned by a SINGLE camera pipeline.

    Accumulates frame rates, operational latencies, transport counters, and
    thread states, producing immutable PipelineMetrics snapshots.

    Args:
        pipeline_id: Unique pipeline identifier.
        camera_id: Target camera identifier.
        camera_name: Descriptive camera name.
        queue_capacity: Buffer queue capacity bound.
    """

    def __init__(
        self,
        pipeline_id: str,
        camera_id: str = "",
        camera_name: str = "",
        queue_capacity: int = 30,
    ) -> None:
        self._pipeline_id = pipeline_id
        self._camera_id = camera_id
        self._camera_name = camera_name
        self._queue_capacity = queue_capacity

        self._lock = threading.Lock()

        # Operational Latency Accumulators
        self._read_latency_acc = RollingMetricsAccumulator(capacity=50)
        self._detection_latency_acc = RollingMetricsAccumulator(capacity=50)
        self._tracking_latency_acc = RollingMetricsAccumulator(capacity=50)
        self._pipeline_latency_acc = RollingMetricsAccumulator(capacity=50)

        # Counters & Rates
        self._fps_reader: float = 0.0
        self._fps_execution: float = 0.0
        self._frames_processed: int = 0
        self._frames_dropped: int = 0
        self._queue_size_current: int = 0
        self._active_detections_count: int = 0
        self._active_tracks_count: int = 0
        self._active_zones_count: int = 0

        # System Hardware & Thread Flags
        self._gpu_utilization_pct: float = 0.0
        self._gpu_memory_used_mb: float = 0.0
        self._cpu_utilization_pct: float = 0.0
        self._ram_used_mb: float = 0.0
        self._thread_reader_alive: bool = True
        self._thread_execution_alive: bool = True
        self._thread_snapshot_alive: bool = True

    @property
    def pipeline_id(self) -> str:
        """Pipeline identifier."""
        return self._pipeline_id

    def update_reader_fps(self, fps: float) -> None:
        """Update RTSP frame ingestion FPS."""
        with self._lock:
            self._fps_reader = float(fps)

    def update_execution(self, fps: float, pipeline_latency_ms: float) -> None:
        """Update processing FPS and total pipeline latency sample."""
        with self._lock:
            self._fps_execution = float(fps)
            self._frames_processed += 1
            self._pipeline_latency_acc.add(pipeline_latency_ms)

    def update_stage_latencies(
        self,
        read_ms: float = 0.0,
        detection_ms: float = 0.0,
        tracking_ms: float = 0.0,
    ) -> None:
        """Update individual AI inference stage latency samples."""
        with self._lock:
            if read_ms > 0:
                self._read_latency_acc.add(read_ms)
            if detection_ms > 0:
                self._detection_latency_acc.add(detection_ms)
            if tracking_ms > 0:
                self._tracking_latency_acc.add(tracking_ms)

    def update_counts(
        self,
        detections_count: int,
        tracks_count: int,
        zones_count: int = 0,
    ) -> None:
        """Update active detection, track, and spatial zone counts."""
        with self._lock:
            self._active_detections_count = int(detections_count)
            self._active_tracks_count = int(tracks_count)
            if zones_count > 0:
                self._active_zones_count = int(zones_count)

    def update_transport(self, queue_size: int, dropped_delta: int = 0) -> None:
        """Update queue depth and dropped frame counts."""
        with self._lock:
            self._queue_size_current = int(queue_size)
            if dropped_delta > 0:
                self._frames_dropped += dropped_delta

    def update_thread_states(
        self,
        reader_alive: Optional[bool] = None,
        execution_alive: Optional[bool] = None,
        snapshot_alive: Optional[bool] = None,
    ) -> None:
        """Update background thread vitality flags."""
        with self._lock:
            if reader_alive is not None:
                self._thread_reader_alive = reader_alive
            if execution_alive is not None:
                self._thread_execution_alive = execution_alive
            if snapshot_alive is not None:
                self._thread_snapshot_alive = snapshot_alive

    def snapshot(self) -> PipelineMetrics:
        """Construct an immutable PipelineMetrics snapshot representing current state.

        Returns:
            Immutable PipelineMetrics dataclass instance.
        """
        with self._lock:
            return PipelineMetrics(
                pipeline_id=self._pipeline_id,
                camera_id=self._camera_id,
                camera_name=self._camera_name,
                fps_reader=self._fps_reader,
                fps_execution=self._fps_execution,
                frames_processed=self._frames_processed,
                frames_dropped=self._frames_dropped,
                queue_size_current=self._queue_size_current,
                queue_capacity=self._queue_capacity,
                latency_read_ms=self._read_latency_acc.get_average(),
                latency_detection_ms=self._detection_latency_acc.get_average(),
                latency_tracking_ms=self._tracking_latency_acc.get_average(),
                latency_pipeline_ms=self._pipeline_latency_acc.get_average(),
                active_detections_count=self._active_detections_count,
                active_tracks_count=self._active_tracks_count,
                active_zones_count=self._active_zones_count,
                gpu_utilization_pct=self._gpu_utilization_pct,
                gpu_memory_used_mb=self._gpu_memory_used_mb,
                cpu_utilization_pct=self._cpu_utilization_pct,
                ram_used_mb=self._ram_used_mb,
                thread_reader_alive=self._thread_reader_alive,
                thread_execution_alive=self._thread_execution_alive,
                thread_snapshot_alive=self._thread_snapshot_alive,
                timestamp_utc=time.time(),
            )

