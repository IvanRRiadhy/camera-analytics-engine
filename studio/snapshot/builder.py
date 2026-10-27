"""
SnapshotBuilder Infrastructure (Sprint H1.5D1.5).

Constructs immutable EngineStudioSnapshot objects from raw collector outputs and provides
on_snapshot_created callback hooks for telemetry recording and replay engines.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Callable, Optional

from camera_analytics.studio.snapshot.engine_studio_snapshot import (
    CameraSnapshot,
    CommunicationSnapshot,
    ConfigurationSnapshot,
    EngineStudioSnapshot,
    EventTimelineSnapshot,
    HumanSnapshot,
    ModelSnapshot,
    ModuleSnapshot,
    PipelineSnapshot,
    ProfilerSnapshot,
    RuntimeSnapshot,
    SnapshotMetadata,
    ThreadSnapshot,
    ZoneSnapshot,
)

logger = logging.getLogger(__name__)


class SnapshotBuilder:
    """Builder constructing immutable EngineStudioSnapshot objects and notifying subscribers."""

    def __init__(self) -> None:
        self._listeners: list[Callable[[EngineStudioSnapshot], None]] = []

    def register_on_snapshot_created_hook(self, listener: Callable[[EngineStudioSnapshot], None]) -> None:
        """Register a callback hook triggered when a new snapshot is built."""
        self._listeners.append(listener)

    def build(
        self,
        sequence_id: int,
        generation_time_ms: float,
        collector_count: int,
        collector_success_count: int,
        collector_failed_count: int,
        collector_timeout_count: int,
        runtime: Optional[RuntimeSnapshot] = None,
        pipeline: Optional[PipelineSnapshot] = None,
        model: Optional[ModelSnapshot] = None,
        human: Optional[HumanSnapshot] = None,
        zone: Optional[ZoneSnapshot] = None,
        module: Optional[ModuleSnapshot] = None,
        communication: Optional[CommunicationSnapshot] = None,
        profiler: Optional[ProfilerSnapshot] = None,
        thread: Optional[ThreadSnapshot] = None,
        configuration: Optional[ConfigurationSnapshot] = None,
        camera: Optional[CameraSnapshot] = None,
        event_timeline: Optional[EventTimelineSnapshot] = None,
    ) -> EngineStudioSnapshot:
        """Construct immutable EngineStudioSnapshot and invoke subscribers."""
        meta = SnapshotMetadata(
            snapshot_id=str(uuid.uuid4()),
            sequence_number=sequence_id,
            snapshot_schema_version="2.0.0",
            timestamp_utc=time.time(),
            snapshot_generation_time_ms=generation_time_ms,
            collector_count=collector_count,
            collector_success_count=collector_success_count,
            collector_failed_count=collector_failed_count,
            collector_timeout_count=collector_timeout_count,
        )

        snapshot = EngineStudioSnapshot(
            metadata=meta,
            timestamp_utc=meta.timestamp_utc,
            sequence_id=sequence_id,
            runtime=runtime or RuntimeSnapshot(),
            pipeline=pipeline or PipelineSnapshot(),
            model=model or ModelSnapshot(),
            human=human or HumanSnapshot(),
            zone=zone or ZoneSnapshot(),
            module=module or ModuleSnapshot(),
            communication=communication or CommunicationSnapshot(),
            profiler=profiler or ProfilerSnapshot(),
            thread=thread or ThreadSnapshot(),
            configuration=configuration or ConfigurationSnapshot(),
            camera=camera or CameraSnapshot(),
            event_timeline=event_timeline or EventTimelineSnapshot(),
        )

        # Notify hooks (e.g. TelemetryRecorder)
        for listener in self._listeners:
            try:
                listener(snapshot)
            except Exception as e:
                logger.error(f"[SnapshotBuilder] Hook execution failed: {e}")

        return snapshot
