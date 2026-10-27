"""
EngineStudioSnapshot Container Infrastructure (Sprint H1.5D1).

Immutable snapshot objects holding all subsystem metric snapshots.
All Pure View Inspector panels receive EngineStudioSnapshot and render UI without touching engine internals.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence


@dataclass(frozen=True, slots=True)
class SnapshotMetadata:
    """Immutable snapshot header metadata containing UUID, schema version, and diagnostic telemetry."""

    snapshot_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sequence_number: int = 0
    snapshot_schema_version: str = "2.0.0"
    timestamp_utc: float = field(default_factory=time.time)
    snapshot_generation_time_ms: float = 0.0
    collector_count: int = 12
    collector_success_count: int = 12
    collector_failed_count: int = 0
    collector_timeout_count: int = 0
    engine_fps: float = 30.0
    engine_mode: str = "standalone"
    studio_version: str = "2.0.0"


@dataclass(frozen=True, slots=True)
class RuntimeSnapshot:
    overall_fps: float = 30.0
    frame_time_ms: float = 33.3
    pipeline_latency_ms: float = 18.4
    cpu_utilization_pct: float = 14.2
    ram_usage_mb: float = 1420.0
    gpu_memory_vram_mb: float = 840.5
    gpu_compute_utilization_pct: float = 32.0
    gpu_device_name: str = "NVIDIA CUDA GPU"
    frame_queue_size: int = 4
    frame_queue_capacity: int = 30
    dropped_frames_count: int = 0
    inference_queue_size: int = 2
    snapshot_queue_size: int = 1
    communication_queue_size: int = 0


@dataclass(frozen=True, slots=True)
class PipelineStageSnapshot:
    stage_name: str
    status: str = "RUNNING"
    latency_ms: float = 0.0
    avg_latency_ms: float = 0.0
    errors_count: int = 0
    queue_size: int = 0
    dropped_count: int = 0


@dataclass(frozen=True, slots=True)
class PipelineSnapshot:
    active_pipelines_count: int = 2
    stages: tuple[PipelineStageSnapshot, ...] = ()


@dataclass(frozen=True, slots=True)
class ModelEntrySnapshot:
    model_id: str
    status: str = "ACTIVE"
    backend: str = "pytorch"
    device: str = "cuda:0"
    is_fp16: bool = True
    vram_mb: float = 312.8
    avg_latency_ms: float = 24.38
    p95_latency_ms: float = 25.1
    batch_size: int = 4
    success_count: int = 12840
    failure_count: int = 0


@dataclass(frozen=True, slots=True)
class ModelSnapshot:
    loaded_models: tuple[ModelEntrySnapshot, ...] = ()


@dataclass(frozen=True, slots=True)
class TrackSnapshot:
    track_id: int
    lifecycle: str = "STABLE"
    age: float = 28.5
    ema_age: float = 28.4
    gender: str = "male"
    confidence: float = 0.92
    quality_score: float = 0.88
    zone: str = "zone_lobby_entry"
    lifetime_s: float = 45.2
    inference_count: int = 180


@dataclass(frozen=True, slots=True)
class HumanSnapshot:
    active_tracks_count: int = 0
    tracks: tuple[TrackSnapshot, ...] = ()


@dataclass(frozen=True, slots=True)
class ZoneEntrySnapshot:
    zone_id: str
    zone_name: str
    people_count: int = 0
    occupancy_state: str = "NORMAL"
    queue_length: int = 0
    loitering_alerts_count: int = 0


@dataclass(frozen=True, slots=True)
class ZoneSnapshot:
    active_zones_count: int = 0
    zones: tuple[ZoneEntrySnapshot, ...] = ()


@dataclass(frozen=True, slots=True)
class ModuleEntrySnapshot:
    module_id: str
    status: str = "ACTIVE"
    priority: int = 1
    frame_stride: int = 1
    cooldown_s: float = 0.0
    execution_count: int = 42150
    skipped_count: int = 0
    quality_rejections_count: int = 0
    last_exec_latency_ms: float = 0.05


@dataclass(frozen=True, slots=True)
class ModuleSnapshot:
    active_modules: tuple[ModuleEntrySnapshot, ...] = ()


@dataclass(frozen=True, slots=True)
class CommunicationPublisherSnapshot:
    publisher_type: str
    enabled: bool = True
    status: str = "ACTIVE"
    queue_depth: int = 0
    queue_capacity: int = 100
    sent_count: int = 4215
    failures_count: int = 0
    reconnects_count: int = 0
    heartbeat_latency_s: float = 1.0


@dataclass(frozen=True, slots=True)
class CommunicationSnapshot:
    publishers: tuple[CommunicationPublisherSnapshot, ...] = ()


@dataclass(frozen=True, slots=True)
class ProfilerSnapshot:
    total_frame_time_ms: float = 33.36
    detection_latency_ms: float = 14.80
    inference_latency_ms: float = 24.38
    tracking_latency_ms: float = 0.12
    human_runtime_latency_ms: float = 0.40
    rendering_latency_ms: float = 3.10


@dataclass(frozen=True, slots=True)
class ThreadEntrySnapshot:
    thread_name: str
    thread_type: str
    status: str = "RUNNING"
    target_fps: float = 30.0
    actual_fps: float = 29.8
    cpu_utilization_pct: float = 3.2
    queue_depth: int = 4


@dataclass(frozen=True, slots=True)
class ThreadSnapshot:
    active_threads: tuple[ThreadEntrySnapshot, ...] = ()


@dataclass(frozen=True, slots=True)
class ConfigDiffEntrySnapshot:
    param_name: str
    default_value: Any
    current_value: Any
    is_modified: bool = False


@dataclass(frozen=True, slots=True)
class ConfigurationSnapshot:
    config_file_path: str = "configs/standalone.json"
    engine_id: str = "engine_standalone_01"
    device: str = "cuda:0"
    max_target_fps: float = 30.0
    diffs: tuple[ConfigDiffEntrySnapshot, ...] = ()


@dataclass(frozen=True, slots=True)
class CameraEntrySnapshot:
    camera_id: str
    rtsp_url: str
    status: str = "CONNECTED"
    reconnect_count: int = 0
    fps: float = 29.8
    bitrate_kbps: float = 4096.0
    packet_loss_pct: float = 0.0
    latency_ms: float = 12.0
    resolution: str = "1920x1080"
    dropped_frames_count: int = 0


@dataclass(frozen=True, slots=True)
class CameraSnapshot:
    active_cameras: tuple[CameraEntrySnapshot, ...] = ()


@dataclass(frozen=True, slots=True)
class EventEntrySnapshot:
    timestamp_formatted: str
    event_type: str
    track_id: int
    message: str


@dataclass(frozen=True, slots=True)
class EventTimelineSnapshot:
    recent_events: tuple[EventEntrySnapshot, ...] = ()


@dataclass(frozen=True, slots=True)
class EngineStudioSnapshot:
    """Immutable top-level container holding all 12 subsystem snapshot objects and metadata."""

    metadata: SnapshotMetadata = field(default_factory=SnapshotMetadata)
    timestamp_utc: float = field(default_factory=time.time)
    sequence_id: int = 0
    runtime: RuntimeSnapshot = field(default_factory=RuntimeSnapshot)
    pipeline: PipelineSnapshot = field(default_factory=PipelineSnapshot)
    model: ModelSnapshot = field(default_factory=ModelSnapshot)
    human: HumanSnapshot = field(default_factory=HumanSnapshot)
    zone: ZoneSnapshot = field(default_factory=ZoneSnapshot)
    module: ModuleSnapshot = field(default_factory=ModuleSnapshot)
    communication: CommunicationSnapshot = field(default_factory=CommunicationSnapshot)
    profiler: ProfilerSnapshot = field(default_factory=ProfilerSnapshot)
    thread: ThreadSnapshot = field(default_factory=ThreadSnapshot)
    configuration: ConfigurationSnapshot = field(default_factory=ConfigurationSnapshot)
    camera: CameraSnapshot = field(default_factory=CameraSnapshot)
    event_timeline: EventTimelineSnapshot = field(default_factory=EventTimelineSnapshot)
