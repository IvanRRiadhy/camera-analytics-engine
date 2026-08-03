"""
Pipeline Coordinator Component.

High-level orchestrator coordinating PipelineManager, SessionManager, PipelineFactory,
and CameraCatalog. Prevents PipelineManager from becoming a God Class.
"""

from __future__ import annotations

import logging
from typing import Optional

from camera_analytics.bootstrap.models import ConfigurationSnapshot
from camera_analytics.catalog.camera_catalog import CameraCatalog
from camera_analytics.orchestration.factory import PipelineFactory
from camera_analytics.orchestration.instance import PipelineInstance
from camera_analytics.orchestration.pipeline_manager import PipelineManager
from camera_analytics.orchestration.session_manager import SessionManager
from camera_analytics.orchestration.states import CameraSessionState, PipelineState

logger = logging.getLogger(__name__)


class PipelineCoordinatorError(Exception):
    """Raised when high-level pipeline coordination operations fail."""


class PipelineCoordinator:
    """High-level facade orchestrator coordinating camera sessions, pipeline lifecycle, and recovery."""

    def __init__(
        self,
        catalog: CameraCatalog,
        session_manager: Optional[SessionManager] = None,
        pipeline_manager: Optional[PipelineManager] = None,
        factory: Optional[PipelineFactory] = None,
    ) -> None:
        self._catalog = catalog
        self._session_manager = session_manager or SessionManager()
        self._pipeline_manager = pipeline_manager or PipelineManager()
        self._factory = factory or PipelineFactory()

    @property
    def catalog(self) -> CameraCatalog:
        return self._catalog

    @property
    def session_manager(self) -> SessionManager:
        return self._session_manager

    @property
    def pipeline_manager(self) -> PipelineManager:
        return self._pipeline_manager

    def initialize_pipelines_from_snapshot(self, snapshot: ConfigurationSnapshot) -> list[PipelineInstance]:
        """Construct and initialize PipelineInstances and CameraSessions for all snapshot pipelines.

        Args:
            snapshot: Validated ConfigurationSnapshot instance.

        Returns:
            List of initialized PipelineInstances.
        """
        initialized: list[PipelineInstance] = []

        for pipe_cfg in snapshot.pipelines:
            if not pipe_cfg.enabled:
                logger.info("PipelineCoordinator: Pipeline '%s' is disabled, skipping.", pipe_cfg.pipeline_id)
                continue

            camera = self._catalog.get_required_camera(pipe_cfg.camera_id)
            session = self._session_manager.create_session(camera_id=camera.camera_id, rtsp_uri=camera.source)
            from camera_analytics.core.spatial.zone_manager import ZoneManager
            from camera_analytics.core.zone_engine import ZoneEngine
            from camera_analytics.runtime.analytics import PipelineAnalyticsAggregator

            z_mgr = ZoneManager(default_resolution=(camera.width or 1920, camera.height or 1080))
            raw_zones = getattr(camera, "raw_zones_payload", [])
            z_mgr.load_zones_from_backend(camera.camera_id, raw_zones)

            z_engine = ZoneEngine(zone_manager=z_mgr)
            aggregator = PipelineAnalyticsAggregator(camera_id=camera.camera_id, pipeline_id=pipe_cfg.pipeline_id)

            instance = self._factory.create_instance(config=pipe_cfg, session=session, camera=camera)
            object.__setattr__(instance, "zone_manager", z_mgr)
            object.__setattr__(instance, "zone_engine", z_engine)
            object.__setattr__(instance, "aggregator", aggregator)

            self._pipeline_manager.add_pipeline(instance)
            initialized.append(instance)
            logger.info(
                "PipelineCoordinator: Initialized pipeline '%s' with isolated ZoneManager & ZoneEngine (Camera: %s, GPU: %d, Active Zones: %d)",
                instance.pipeline_id,
                instance.camera_id,
                instance.gpu_id,
                len(z_mgr.get_zones(camera.camera_id)),
            )

        return initialized

    def start_pipeline(self, pipeline_id: str) -> bool:
        """Start a single pipeline and activate its session.

        Args:
            pipeline_id: Target pipeline identifier string.

        Returns:
            True if started, False otherwise.
        """
        instance = self._pipeline_manager.get_pipeline(pipeline_id)
        if instance is None:
            logger.warning("PipelineCoordinator: Cannot start non-existent pipeline '%s'", pipeline_id)
            return False

        # Activate Session -> READY
        updated_sess = self._session_manager.activate_session(instance.session.session_id)
        updated_sess = self._session_manager.start_session(updated_sess.session_id)

        # Update Pipeline directly to RUNNING
        running_instance = instance.with_state(PipelineState.RUNNING, session=updated_sess)
        self._pipeline_manager.add_pipeline(running_instance)

        logger.info("PipelineCoordinator: Started pipeline '%s' -> RUNNING", pipeline_id)
        return True

    def stop_pipeline(self, pipeline_id: str) -> bool:
        """Stop a running pipeline and suspend/stop its session."""
        instance = self._pipeline_manager.get_pipeline(pipeline_id)
        if instance is None:
            return False

        updated_sess = self._session_manager.stop_session(instance.session.session_id)
        stopped_instance = instance.with_state(PipelineState.STOPPED, session=updated_sess)
        self._pipeline_manager.add_pipeline(stopped_instance)

        logger.info("PipelineCoordinator: Stopped pipeline '%s' -> STOPPED", pipeline_id)
        return True

    def restart_pipeline(self, pipeline_id: str) -> bool:
        """Restart a pipeline and recover its session."""
        logger.info("PipelineCoordinator: Restarting pipeline '%s'...", pipeline_id)
        self.stop_pipeline(pipeline_id)
        return self.start_pipeline(pipeline_id)

    def start_all_pipelines(self) -> int:
        """Start all registered pipelines."""
        started = 0
        for inst in self._pipeline_manager.list_pipelines():
            if self.start_pipeline(inst.pipeline_id):
                started += 1
        logger.info("PipelineCoordinator: Started %d pipeline(s)", started)
        return started

    def stop_all_pipelines(self) -> int:
        """Stop all registered pipelines."""
        stopped = 0
        for inst in self._pipeline_manager.list_pipelines():
            if self.stop_pipeline(inst.pipeline_id):
                stopped += 1
        logger.info("PipelineCoordinator: Stopped %d pipeline(s)", stopped)
        return stopped

    def get_pipeline_status_summary(self, pipeline_id: str) -> Optional[dict[str, object]]:
        """Get status summary dictionary for a pipeline."""
        instance = self._pipeline_manager.get_pipeline(pipeline_id)
        if instance is None:
            return None

        return {
            "pipeline_id": instance.pipeline_id,
            "camera_id": instance.camera_id,
            "gpu_id": instance.gpu_id,
            "pipeline_state": instance.state.name,
            "session_id": instance.session.session_id,
            "session_state": instance.session.state.name,
            "connection_alive": instance.session.connection.is_alive,
            "error_message": instance.error_message or instance.session.error_message,
        }
