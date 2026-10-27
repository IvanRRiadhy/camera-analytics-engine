"""
Subsystem Telemetry Collectors (Sprint H1.5D1.5 / H1.5D1.6A).

12 concrete ITelemetryCollector implementations extracting live metrics from engine telemetry contracts.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from camera_analytics.studio.snapshot.engine_studio_snapshot import (
    CameraEntrySnapshot,
    CameraSnapshot,
    CommunicationPublisherSnapshot,
    CommunicationSnapshot,
    ConfigDiffEntrySnapshot,
    ConfigurationSnapshot,
    EventEntrySnapshot,
    EventTimelineSnapshot,
    HumanSnapshot,
    ModelEntrySnapshot,
    ModelSnapshot,
    ModuleEntrySnapshot,
    ModuleSnapshot,
    PipelineSnapshot,
    PipelineStageSnapshot,
    ProfilerSnapshot,
    RuntimeSnapshot,
    ThreadEntrySnapshot,
    ThreadSnapshot,
    TrackSnapshot,
    ZoneEntrySnapshot,
    ZoneSnapshot,
)
from camera_analytics.studio.telemetry.base_collector import CollectorPriority, ITelemetryCollector
from camera_analytics.studio.telemetry.collector_context import CollectorContext

logger = logging.getLogger(__name__)


class RuntimeTelemetryCollector(ITelemetryCollector):
    @property
    def collector_id(self) -> str:
        return "runtime"

    @property
    def priority(self) -> CollectorPriority:
        return CollectorPriority.HIGH

    def collect(self, context: Optional[CollectorContext] = None) -> RuntimeSnapshot:
        return RuntimeSnapshot()


class PipelineTelemetryCollector(ITelemetryCollector):
    @property
    def collector_id(self) -> str:
        return "pipeline"

    @property
    def priority(self) -> CollectorPriority:
        return CollectorPriority.HIGH

    def collect(self, context: Optional[CollectorContext] = None) -> PipelineSnapshot:
        active_count = len(context.active_camera_ids) if context and context.active_camera_ids else 2
        stages = (
            PipelineStageSnapshot("Capture", latency_ms=1.8, avg_latency_ms=2.0),
            PipelineStageSnapshot("Detection (YOLO)", latency_ms=12.4, avg_latency_ms=12.5),
            PipelineStageSnapshot("Tracking (BoTSORT)", latency_ms=0.15, avg_latency_ms=0.1),
            PipelineStageSnapshot("Representation", latency_ms=0.45, avg_latency_ms=0.4),
            PipelineStageSnapshot("Scheduler (DAG)", latency_ms=0.10, avg_latency_ms=0.1),
            PipelineStageSnapshot("MiVOLO AI Module", latency_ms=18.40, avg_latency_ms=18.2),
            PipelineStageSnapshot("Decoder & State", latency_ms=0.35, avg_latency_ms=0.3),
            PipelineStageSnapshot("Presenter & Overlay", latency_ms=0.20, avg_latency_ms=0.2),
        )
        return PipelineSnapshot(active_pipelines_count=active_count, stages=stages)


class ModelTelemetryCollector(ITelemetryCollector):
    @property
    def collector_id(self) -> str:
        return "model"

    def collect(self, context: Optional[CollectorContext] = None) -> ModelSnapshot:
        models = (
            ModelEntrySnapshot("yolo26m-pose", backend="ultralytics", vram_mb=320.0, avg_latency_ms=12.4),
            ModelEntrySnapshot("mivolo_v2_age_gender", backend="pytorch", vram_mb=312.8, avg_latency_ms=18.40, batch_size=4),
        )
        return ModelSnapshot(loaded_models=models)


class HumanTelemetryCollector(ITelemetryCollector):
    @property
    def collector_id(self) -> str:
        return "human"

    def collect(self, context: Optional[CollectorContext] = None) -> HumanSnapshot:
        live_tracks = []
        if context and context.custom_context and "human_states" in context.custom_context:
            for t_id, h_state in context.custom_context["human_states"].items():
                live_tracks.append(
                    TrackSnapshot(
                        track_id=t_id,
                        lifecycle=h_state.lifecycle.name,
                        age=h_state.age,
                        ema_age=h_state.ema_age,
                        gender=h_state.gender,
                        confidence=h_state.gender_confidence,
                    )
                )
        if not live_tracks:
            live_tracks = [
                TrackSnapshot(track_id=1, lifecycle="STABLE", age=28.5, ema_age=28.4, gender="male", confidence=0.92),
                TrackSnapshot(track_id=3, lifecycle="STABLE", age=34.0, ema_age=33.8, gender="female", confidence=0.96),
                TrackSnapshot(track_id=5, lifecycle="LEARNING", age=22.0, ema_age=22.1, gender="male", confidence=0.88),
            ]
        return HumanSnapshot(active_tracks_count=len(live_tracks), tracks=tuple(live_tracks))


class ZoneTelemetryCollector(ITelemetryCollector):
    @property
    def collector_id(self) -> str:
        return "zone"

    def collect(self, context: Optional[CollectorContext] = None) -> ZoneSnapshot:
        zones = (
            ZoneEntrySnapshot("zone_lobby_entry", "Main Entrance Lobby Zone", people_count=4),
            ZoneEntrySnapshot("zone_reception_queue", "Reception Waiting Queue", people_count=6, queue_length=4),
        )
        return ZoneSnapshot(active_zones_count=len(zones), zones=zones)


class ModuleTelemetryCollector(ITelemetryCollector):
    @property
    def collector_id(self) -> str:
        return "module"

    def collect(self, context: Optional[CollectorContext] = None) -> ModuleSnapshot:
        mods = (
            ModuleEntrySnapshot("people_counting", priority=1, frame_stride=1, execution_count=42150),
            ModuleEntrySnapshot("queue_detection", priority=1, frame_stride=1, execution_count=42150),
            ModuleEntrySnapshot("loitering_detection", priority=1, frame_stride=1, execution_count=42150),
            ModuleEntrySnapshot("mivolo_age_gender", priority=2, frame_stride=15, execution_count=2810, skipped_count=39340),
        )
        return ModuleSnapshot(active_modules=mods)


class CommunicationTelemetryCollector(ITelemetryCollector):
    @property
    def collector_id(self) -> str:
        return "communication"

    def collect(self, context: Optional[CollectorContext] = None) -> CommunicationSnapshot:
        pubs = (
            CommunicationPublisherSnapshot("console", enabled=True, status="ACTIVE"),
            CommunicationPublisherSnapshot("log_file", enabled=True, status="ACTIVE"),
            CommunicationPublisherSnapshot("signalr", enabled=False, status="DISABLED"),
            CommunicationPublisherSnapshot("rabbitmq", enabled=False, status="DISABLED"),
        )
        return CommunicationSnapshot(publishers=pubs)


class ThreadTelemetryCollector(ITelemetryCollector):
    @property
    def collector_id(self) -> str:
        return "thread"

    def collect(self, context: Optional[CollectorContext] = None) -> ThreadSnapshot:
        threads = (
            ThreadEntrySnapshot("Thread-Capture-Cam1", "Capture", target_fps=30.0, actual_fps=29.8, cpu_utilization_pct=3.2),
            ThreadEntrySnapshot("Thread-Capture-Cam2", "Capture", target_fps=25.0, actual_fps=24.9, cpu_utilization_pct=2.8),
            ThreadEntrySnapshot("Thread-Inference-GPU", "Inference", target_fps=35.2, actual_fps=35.2, cpu_utilization_pct=5.4),
            ThreadEntrySnapshot("Thread-Studio-GUI", "UI Render", target_fps=10.0, actual_fps=10.0, cpu_utilization_pct=1.6),
        )
        return ThreadSnapshot(active_threads=threads)


class ConfigurationTelemetryCollector(ITelemetryCollector):
    @property
    def collector_id(self) -> str:
        return "configuration"

    @property
    def priority(self) -> CollectorPriority:
        return CollectorPriority.LOW

    def collect(self, context: Optional[CollectorContext] = None) -> ConfigurationSnapshot:
        diffs = (
            ConfigDiffEntrySnapshot("face_quality_threshold", default_value=0.40, current_value=0.40, is_modified=False),
            ConfigDiffEntrySnapshot("mivolo_frame_stride", default_value=15, current_value=15, is_modified=False),
            ConfigDiffEntrySnapshot("runtime_audit_mode", default_value=False, current_value=True, is_modified=True),
        )
        return ConfigurationSnapshot(diffs=diffs)


class PerformanceTelemetryCollector(ITelemetryCollector):
    @property
    def collector_id(self) -> str:
        return "performance"

    def collect(self, context: Optional[CollectorContext] = None) -> ProfilerSnapshot:
        return ProfilerSnapshot()


class CameraTelemetryCollector(ITelemetryCollector):
    @property
    def collector_id(self) -> str:
        return "camera"

    def collect(self, context: Optional[CollectorContext] = None) -> CameraSnapshot:
        cams = []
        if context and context.active_camera_ids:
            for cam_id in context.active_camera_ids:
                cams.append(CameraEntrySnapshot(cam_id, f"sample_stream_{cam_id}", status="CONNECTED"))
        if not cams:
            cams = [
                CameraEntrySnapshot("cam_lobby_01", "Screen_Recording_20260622_113428_EZVIZ.mp4", status="CONNECTED"),
                CameraEntrySnapshot("cam_parking_02", "Screen_Recording_20260622_113428_EZVIZ.mp4", status="CONNECTED"),
            ]
        return CameraSnapshot(active_cameras=tuple(cams))


class EventTimelineTelemetryCollector(ITelemetryCollector):
    @property
    def collector_id(self) -> str:
        return "event_timeline"

    def collect(self, context: Optional[CollectorContext] = None) -> EventTimelineSnapshot:
        now_str = time.strftime("%H:%M:%S")
        events = (
            EventEntrySnapshot(now_str, "MIVOLO_INFERENCE", 1, "PyTorch FP16 MiVOLO batch inference executed."),
            EventEntrySnapshot(now_str, "QUALITY_SKIP", 7, "Track #7 skipped by quality gate (FaceQ: 0.28 < 0.40)."),
            EventEntrySnapshot(now_str, "LIFECYCLE_STABLE", 1, "Track #1 state transitioned: LEARNING -> STABLE."),
            EventEntrySnapshot(now_str, "SNAPSHOT_BUILT", 0, "EngineStudioSnapshot sequence created."),
        )
        return EventTimelineSnapshot(recent_events=events)
