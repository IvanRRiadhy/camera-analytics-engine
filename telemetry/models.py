"""
Telemetry Models.

Defines decoupled, immutable data models for operational pipeline metrics,
session performance counters, and aggregated telemetry snapshots.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True, slots=True)
class MetricValue:
    """Single timestamped numerical sample value."""

    timestamp_utc: float
    value: float


@dataclass(frozen=True, slots=True)
class PipelineMetrics:
    """Immutable operational metrics snapshot for a single camera pipeline.

    Attributes:
        pipeline_id: Unique pipeline identifier.
        camera_id: Target camera identifier.
        camera_name: Descriptive camera name.
        fps_reader: Ingestion frame rate.
        fps_execution: Processing frame rate.
        frames_processed: Cumulative processed frame count.
        frames_dropped: Cumulative dropped frame count.
        queue_size_current: Current transport queue depth.
        queue_capacity: Transport queue capacity bound.
        latency_read_ms: Frame ingestion latency in milliseconds.
        latency_detection_ms: YOLO detection latency in milliseconds.
        latency_tracking_ms: BoT-SORT tracking latency in milliseconds.
        latency_pipeline_ms: Total pipeline latency in milliseconds.
        active_detections_count: Current frame detection count.
        active_tracks_count: Current frame active track count.
        active_zones_count: Number of configured spatial zones.
        gpu_utilization_pct: GPU compute utilization percentage.
        gpu_memory_used_mb: GPU VRAM allocation in megabytes.
        cpu_utilization_pct: CPU usage percentage.
        ram_used_mb: System RAM usage in megabytes.
        thread_reader_alive: Whether ReaderWorker thread is active.
        thread_execution_alive: Whether PipelineExecutionWorker thread is active.
        thread_snapshot_alive: Whether SnapshotPublisher thread is active.
        timestamp_utc: Timestamp of metric capture.
    """

    pipeline_id: str
    camera_id: str = ""
    camera_name: str = ""
    fps_reader: float = 0.0
    fps_execution: float = 0.0
    frames_processed: int = 0
    frames_dropped: int = 0
    queue_size_current: int = 0
    queue_capacity: int = 30
    latency_read_ms: float = 0.0
    latency_detection_ms: float = 0.0
    latency_tracking_ms: float = 0.0
    latency_pipeline_ms: float = 0.0
    active_detections_count: int = 0
    active_tracks_count: int = 0
    active_zones_count: int = 0
    gpu_utilization_pct: float = 0.0
    gpu_memory_used_mb: float = 0.0
    cpu_utilization_pct: float = 0.0
    ram_used_mb: float = 0.0
    thread_reader_alive: bool = True
    thread_execution_alive: bool = True
    thread_snapshot_alive: bool = True
    timestamp_utc: float = field(default_factory=time.time)


@dataclass(frozen=True, slots=True)
class PipelineSessionMetrics:
    """Immutable aggregate session statistics since pipeline initialization.

    Attributes:
        session_id: Active orchestration session identifier.
        pipeline_id: Target pipeline identifier.
        start_time_utc: Timestamp when session started.
        total_frames_ingested: Total frames pulled from RTSP stream.
        total_frames_processed: Total frames passed through AI pipeline.
        total_events_emitted: Total analytics events dispatched.
        average_pipeline_fps: Average processing FPS across entire session.
        peak_latency_ms: Maximum recorded pipeline latency in milliseconds.
    """

    session_id: str
    pipeline_id: str
    start_time_utc: float
    total_frames_ingested: int = 0
    total_frames_processed: int = 0
    total_events_emitted: int = 0
    average_pipeline_fps: float = 0.0
    peak_latency_ms: float = 0.0


@dataclass(frozen=True, slots=True)
class MetricsSnapshot:
    """Immutable point-in-time metrics snapshot aggregating system and pipeline states.

    Attributes:
        engine_id: AI Engine node identifier.
        timestamp_utc: Timestamp of metrics aggregation.
        pipeline_metrics: Mapping of pipeline_id to PipelineMetrics model.
        session_metrics: Mapping of pipeline_id to PipelineSessionMetrics model.
        system_metadata: Metadata dict containing environment flags.
    """

    engine_id: str
    timestamp_utc: float = field(default_factory=time.time)
    pipeline_metrics: dict[str, PipelineMetrics] = field(default_factory=dict)
    session_metrics: dict[str, PipelineSessionMetrics] = field(default_factory=dict)
    system_metadata: dict[str, Any] = field(default_factory=dict)

