"""
Pipeline Factory Component.

Factory pattern implementation for constructing isolated PipelineInstance entities.
"""

from __future__ import annotations

from camera_analytics.bootstrap.models import PipelineConfiguration
from camera_analytics.models.camera import Camera
from camera_analytics.orchestration.instance import PipelineInstance
from camera_analytics.orchestration.session import CameraSession
from camera_analytics.orchestration.states import PipelineState


class PipelineFactory:
    """Factory responsible for instantiating PipelineInstance objects."""

    @staticmethod
    def create_instance(
        config: PipelineConfiguration,
        session: CameraSession,
        camera: Camera,
    ) -> PipelineInstance:
        """Construct a new initialized PipelineInstance.

        Args:
            config: PipelineConfiguration dataclass.
            session: CameraSession domain model.
            camera: Camera domain model.

        Returns:
            New PipelineInstance in INITIALIZED state.
        """
        return PipelineInstance(
            pipeline_id=config.pipeline_id,
            camera_id=config.camera_id,
            gpu_id=config.gpu_id,
            config=config,
            camera=camera,
            session=session,
            state=PipelineState.INITIALIZED,
        )
