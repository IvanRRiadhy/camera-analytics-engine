"""
Runtime Metrics Collector Component.

Centralized thread-safe in-memory store collecting operational metrics across active
camera pipelines.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Optional

from camera_analytics.telemetry.accumulator import RollingMetricsAccumulator
from camera_analytics.telemetry.interfaces import IMetricsCollector
from camera_analytics.telemetry.models import PipelineMetrics

logger = logging.getLogger(__name__)


class RuntimeMetricsCollector(IMetricsCollector):
    """Thread-safe central metrics store aggregating operational data per camera pipeline."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._store: dict[str, PipelineMetrics] = {}
        self._latency_accumulators: dict[str, RollingMetricsAccumulator] = {}

    def _get_or_create(self, pipeline_id: str, camera_id: str = "") -> PipelineMetrics:
        if pipeline_id not in self._store:
            self._store[pipeline_id] = PipelineMetrics(
                pipeline_id=pipeline_id,
                camera_id=camera_id,
            )
            self._latency_accumulators[pipeline_id] = RollingMetricsAccumulator(capacity=100)
        return self._store[pipeline_id]

    def record_reader_fps(self, pipeline_id: str, fps: float) -> None:
        """Record RTSP frame ingestion FPS.

        Args:
            pipeline_id: Pipeline identifier.
            fps: Frame rate float.
        """
        with self._lock:
            m = self._get_or_create(pipeline_id)
            self._store[pipeline_id] = PipelineMetrics(
                pipeline_id=m.pipeline_id,
                camera_id=m.camera_id,
                fps_reader=float(fps),
                fps_execution=m.fps_execution,
                frames_processed=m.frames_processed,
                frames_dropped=m.frames_dropped,
                queue_size_current=m.queue_size_current,
                queue_capacity=m.queue_capacity,
                latency_read_ms=m.latency_read_ms,
                latency_detection_ms=m.latency_detection_ms,
                latency_tracking_ms=m.latency_tracking_ms,
                latency_pipeline_ms=m.latency_pipeline_ms,
                active_detections_count=m.active_detections_count,
                active_tracks_count=m.active_tracks_count,
                active_zones_count=m.active_zones_count,
                gpu_utilization_pct=m.gpu_utilization_pct,
                gpu_memory_used_mb=m.gpu_memory_used_mb,
                cpu_utilization_pct=m.cpu_utilization_pct,
                ram_used_mb=m.ram_used_mb,
                thread_reader_alive=m.thread_reader_alive,
                thread_execution_alive=m.thread_execution_alive,
                thread_snapshot_alive=m.thread_snapshot_alive,
                timestamp_utc=time.time(),
            )

    def record_execution_fps(self, pipeline_id: str, fps: float) -> None:
        """Record AI execution FPS.

        Args:
            pipeline_id: Pipeline identifier.
            fps: Execution frame rate float.
        """
        with self._lock:
            m = self._get_or_create(pipeline_id)
            self._store[pipeline_id] = PipelineMetrics(
                pipeline_id=m.pipeline_id,
                camera_id=m.camera_id,
                fps_reader=m.fps_reader,
                fps_execution=float(fps),
                frames_processed=m.frames_processed + 1,
                frames_dropped=m.frames_dropped,
                queue_size_current=m.queue_size_current,
                queue_capacity=m.queue_capacity,
                latency_read_ms=m.latency_read_ms,
                latency_detection_ms=m.latency_detection_ms,
                latency_tracking_ms=m.latency_tracking_ms,
                latency_pipeline_ms=m.latency_pipeline_ms,
                active_detections_count=m.active_detections_count,
                active_tracks_count=m.active_tracks_count,
                active_zones_count=m.active_zones_count,
                gpu_utilization_pct=m.gpu_utilization_pct,
                gpu_memory_used_mb=m.gpu_memory_used_mb,
                cpu_utilization_pct=m.cpu_utilization_pct,
                ram_used_mb=m.ram_used_mb,
                thread_reader_alive=m.thread_reader_alive,
                thread_execution_alive=m.thread_execution_alive,
                thread_snapshot_alive=m.thread_snapshot_alive,
                timestamp_utc=time.time(),
            )

    def record_pipeline_latency(self, pipeline_id: str, latency_ms: float) -> None:
        """Record total frame pipeline latency in milliseconds.

        Args:
            pipeline_id: Pipeline identifier.
            latency_ms: Latency sample value.
        """
        with self._lock:
            m = self._get_or_create(pipeline_id)
            acc = self._latency_accumulators[pipeline_id]
            acc.add(latency_ms)
            avg_lat = acc.get_average()

            self._store[pipeline_id] = PipelineMetrics(
                pipeline_id=m.pipeline_id,
                camera_id=m.camera_id,
                fps_reader=m.fps_reader,
                fps_execution=m.fps_execution,
                frames_processed=m.frames_processed,
                frames_dropped=m.frames_dropped,
                queue_size_current=m.queue_size_current,
                queue_capacity=m.queue_capacity,
                latency_read_ms=m.latency_read_ms,
                latency_detection_ms=m.latency_detection_ms,
                latency_tracking_ms=m.latency_tracking_ms,
                latency_pipeline_ms=avg_lat,
                active_detections_count=m.active_detections_count,
                active_tracks_count=m.active_tracks_count,
                active_zones_count=m.active_zones_count,
                gpu_utilization_pct=m.gpu_utilization_pct,
                gpu_memory_used_mb=m.gpu_memory_used_mb,
                cpu_utilization_pct=m.cpu_utilization_pct,
                ram_used_mb=m.ram_used_mb,
                thread_reader_alive=m.thread_reader_alive,
                thread_execution_alive=m.thread_execution_alive,
                thread_snapshot_alive=m.thread_snapshot_alive,
                timestamp_utc=time.time(),
            )

    def record_counts(self, pipeline_id: str, detections_count: int, tracks_count: int) -> None:
        """Record active detection and track counts for a frame.

        Args:
            pipeline_id: Pipeline identifier.
            detections_count: Current frame detection count.
            tracks_count: Current frame track count.
        """
        with self._lock:
            m = self._get_or_create(pipeline_id)
            self._store[pipeline_id] = PipelineMetrics(
                pipeline_id=m.pipeline_id,
                camera_id=m.camera_id,
                fps_reader=m.fps_reader,
                fps_execution=m.fps_execution,
                frames_processed=m.frames_processed,
                frames_dropped=m.frames_dropped,
                queue_size_current=m.queue_size_current,
                queue_capacity=m.queue_capacity,
                latency_read_ms=m.latency_read_ms,
                latency_detection_ms=m.latency_detection_ms,
                latency_tracking_ms=m.latency_tracking_ms,
                latency_pipeline_ms=m.latency_pipeline_ms,
                active_detections_count=int(detections_count),
                active_tracks_count=int(tracks_count),
                active_zones_count=m.active_zones_count,
                gpu_utilization_pct=m.gpu_utilization_pct,
                gpu_memory_used_mb=m.gpu_memory_used_mb,
                cpu_utilization_pct=m.cpu_utilization_pct,
                ram_used_mb=m.ram_used_mb,
                thread_reader_alive=m.thread_reader_alive,
                thread_execution_alive=m.thread_execution_alive,
                thread_snapshot_alive=m.thread_snapshot_alive,
                timestamp_utc=time.time(),
            )

    def get_metrics(self, pipeline_id: str) -> Optional[PipelineMetrics]:
        """Retrieve aggregated metrics snapshot for a pipeline.

        Args:
            pipeline_id: Target pipeline identifier.

        Returns:
            PipelineMetrics instance or None if not found.
        """
        with self._lock:
            return self._store.get(pipeline_id)
