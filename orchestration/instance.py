"""
Pipeline Instance Domain Entity.

Extends PipelineInstance to serve as the comprehensive container for all runtime components
(reader, frame queue, detector, tracker, kernel runtime, output providers), while defaulting
references to None for Sprint 11.2.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional

from camera_analytics.bootstrap.models import PipelineConfiguration
from camera_analytics.models.camera import Camera
from camera_analytics.orchestration.session import CameraSession
from camera_analytics.orchestration.states import PipelineState


@dataclass(frozen=True, slots=True)
class PipelineInstance:
    """Comprehensive container for a camera pipeline's configuration, state, and runtime components.

    Attributes:
        pipeline_id: Unique string pipeline identifier.
        camera_id: Target camera identifier string.
        gpu_id: Assigned GPU index.
        config: PipelineConfiguration snapshot.
        camera: Camera domain model snapshot.
        session: CameraSession reference.
        state: Current PipelineState.
        created_at: Epoch timestamp of pipeline creation.
        updated_at: Epoch timestamp of last state transition.
        error_message: Optional error message string.
        
        # Runtime Component Holders (Placeholder None for Sprint 11.2, populated in 11.3+)
        reader: Optional frame source reader reference.
        frame_queue: Optional thread-safe frame queue reference.
        detector: Optional object detector port instance.
        tracker: Optional object tracker port instance.
        runtime_kernel: Optional AnalyticsRuntime kernel instance.
        output_providers: Tuple of output providers bound to this pipeline.
    """

    pipeline_id: str
    camera_id: str
    config: PipelineConfiguration
    camera: Camera
    session: CameraSession
    gpu_id: int = 0
    state: PipelineState = PipelineState.CREATED
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    error_message: Optional[str] = None

    # Runtime Placeholders (Sprint 11.3+)
    reader: Optional[Any] = None
    frame_queue: Optional[Any] = None
    detector: Optional[Any] = None
    tracker: Optional[Any] = None
    runtime_kernel: Optional[Any] = None
    zone_manager: Optional[Any] = None
    zone_engine: Optional[Any] = None
    aggregator: Optional[Any] = None
    output_providers: tuple[Any, ...] = ()

    def with_state(
        self,
        new_state: PipelineState,
        session: Optional[CameraSession] = None,
        error_message: Optional[str] = None,
    ) -> PipelineInstance:
        """Construct a new immutable PipelineInstance with updated state or session."""
        return PipelineInstance(
            pipeline_id=self.pipeline_id,
            camera_id=self.camera_id,
            gpu_id=self.gpu_id,
            config=self.config,
            camera=self.camera,
            session=self.session if session is None else session,
            state=new_state,
            created_at=self.created_at,
            updated_at=time.time(),
            error_message=error_message,
            reader=self.reader,
            frame_queue=self.frame_queue,
            detector=self.detector,
            tracker=self.tracker,
            runtime_kernel=self.runtime_kernel,
            output_providers=self.output_providers,
        )
