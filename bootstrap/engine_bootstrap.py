"""
Engine Bootstrap Orchestrator Component.

Coordinates system startup lifecycle:
    1. Load & validate ConfigurationSnapshot via ConfigurationProvider
    2. Populate ServiceRegistry (CameraCatalog, CommunicationManager, OutputProviders)
    3. Initialize Publisher Plugins via PublisherRegistry & CommunicationManager
    4. Construct EngineContext and transition to READY state.
    5. In Enterprise Mode: Trigger Registration, start Heartbeat loop & Command Receiver.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional, Union

from camera_analytics.bootstrap.context import EngineContext
from camera_analytics.bootstrap.heartbeat_service import EngineHeartbeatService
from camera_analytics.bootstrap.models import ConfigurationSnapshot
from camera_analytics.bootstrap.providers.base import ConfigurationProvider
from camera_analytics.bootstrap.providers.json_provider import JsonConfigurationProvider
from camera_analytics.bootstrap.registration_service import EngineRegistrationService
from camera_analytics.bootstrap.service_registry import ServiceRegistry
from camera_analytics.catalog.camera_catalog import CameraCatalog
from camera_analytics.communication.manager import CommunicationManager
from camera_analytics.communication.publisher_base import EventPublisher
from camera_analytics.communication.registry import PublisherRegistry
from camera_analytics.config.loader import ConfigValidationError
from camera_analytics.models.camera import Camera, CameraStatus
from camera_analytics.orchestration.command_receiver import EngineCommandReceiver
from camera_analytics.output.enterprise_event import EnterpriseEventOutputProvider
from camera_analytics.output.human_console import HumanConsoleOutputProvider

logger = logging.getLogger(__name__)


class BootstrapState(Enum):
    """Lifecycle state machine stages for AI Engine Startup."""

    CREATED = auto()
    LOADING = auto()
    VALIDATING = auto()
    INITIALIZING = auto()
    READY = auto()
    FAILED = auto()


@dataclass(frozen=True, slots=True)
class BootstrapResult:
    """Result payload of the bootstrap initialization process.

    Attributes:
        state: Final BootstrapState.
        context: Optional EngineContext instance (if state == READY).
        error_message: Optional error message string (if state == FAILED).
    """

    state: BootstrapState
    context: Optional[EngineContext] = None
    error_message: Optional[str] = None

    @property
    def is_success(self) -> bool:
        """Whether bootstrap completed successfully in READY state."""
        return self.state == BootstrapState.READY


class EngineBootstrap:
    """Central startup orchestrator for the AI Analytics Engine."""

    def __init__(self, provider: Optional[ConfigurationProvider] = None) -> None:
        self._provider = provider or JsonConfigurationProvider()
        self._state = BootstrapState.CREATED
        self._context: Optional[EngineContext] = None

    @property
    def state(self) -> BootstrapState:
        """Current lifecycle state."""
        return self._state

    @property
    def context(self) -> Optional[EngineContext]:
        """EngineContext instance once READY."""
        return self._context

    def bootstrap(self) -> BootstrapResult:
        """Execute system startup sequence.

        Sequence:
            1. LOADING: Read configuration via provider.
            2. VALIDATING: Validate schema and fields.
            3. INITIALIZING: Initialize CameraCatalog, CommunicationManager, Publishers, OutputProviders.
            4. READY: EngineContext ready for Sprint 11.2 pipeline scheduling.

        Returns:
            BootstrapResult payload.
        """
        logger.info("EngineBootstrap: Starting AI Engine bootstrap process...")

        try:
            # 1. LOADING & VALIDATING Configuration
            self._state = BootstrapState.LOADING
            snapshot = self._provider.load()

            self._state = BootstrapState.VALIDATING
            self._validate_snapshot(snapshot)

            # 2. INITIALIZING Platform, Services, Catalog, Publishers
            self._state = BootstrapState.INITIALIZING
            service_registry = ServiceRegistry()

            # Platform Abstraction & Strategy Factories Activation
            from camera_analytics.platform.backend_factories import InferenceBackendFactory, VideoBackendFactory
            from camera_analytics.platform.factory import PlatformFactory

            platform_obj = PlatformFactory.create_platform()
            platform_obj.initialize()
            platform_obj.verify_environment()

            v_factory = VideoBackendFactory(platform_obj.capabilities)
            inf_factory = InferenceBackendFactory(platform_obj.capabilities)

            service_registry.register("platform", platform_obj)
            service_registry.register("capability_registry", platform_obj.capabilities)
            service_registry.register("video_backend_factory", v_factory)
            service_registry.register("inference_backend_factory", inf_factory)
            service_registry.register("resource_manager", platform_obj.get_resource_manager())

            v_backend_name = "GStreamerBackend" if platform_obj.capabilities.has_capability("gstreamer") else "OpenCVBackend"
            inf_backend_name = "TorchBackend"

            logger.info("==========================================================")
            logger.info("               CCTV ANALYTICS AI ENGINE                   ")
            logger.info("==========================================================")
            logger.info(" OS Platform        : %s", platform_obj.capabilities.get_metadata("os_platform", platform_obj.name))
            logger.info(" Target Environment : %s", platform_obj.target_environment)
            logger.info(" Video Backend      : %s", v_backend_name)
            logger.info(" Inference Backend  : %s", inf_backend_name)
            logger.info(" Build Target       : windows-release")
            logger.info("==========================================================")

            # Build & register CameraCatalog
            camera_catalog = self._build_camera_catalog(snapshot)
            service_registry.register("camera_catalog", camera_catalog)

            # Initialize CommunicationManager & Publishers
            comm_manager = self._initialize_publishers(snapshot)
            service_registry.register("communication_manager", comm_manager)

            # Register OutputProviders
            human_output = HumanConsoleOutputProvider(enabled=True)
            enterprise_output = EnterpriseEventOutputProvider(comm_manager=comm_manager, enabled=True)
            service_registry.register("output_human_console", human_output)
            service_registry.register("output_enterprise_event", enterprise_output)

            # Initialize PipelineCoordinator & Pipeline instances
            from camera_analytics.orchestration.pipeline_coordinator import PipelineCoordinator

            coordinator = PipelineCoordinator(catalog=camera_catalog)
            coordinator.initialize_pipelines_from_snapshot(snapshot)
            service_registry.register("pipeline_coordinator", coordinator)

            # Enterprise Mode Orchestration: Registration, Heartbeats, Command Listening
            is_enterprise = snapshot.engine.mode.lower() == "enterprise" or comm_manager.has_publisher("rabbitmq")
            if is_enterprise:
                logger.info("[+] Enterprise Mode Detected: Triggering Node Registration & Telemetry Services...")

                reg_service = EngineRegistrationService(
                    instance_id=snapshot.engine.engine_id,
                    comm_manager=comm_manager,
                )
                reg_service.register()
                service_registry.register("registration_service", reg_service)

                hb_service = EngineHeartbeatService(
                    instance_id=snapshot.engine.engine_id,
                    comm_manager=comm_manager,
                    pipeline_coordinator=coordinator,
                    interval_sec=5.0,
                )
                hb_service.start()
                service_registry.register("heartbeat_service", hb_service)

                cmd_receiver = EngineCommandReceiver(
                    instance_id=snapshot.engine.engine_id,
                    comm_manager=comm_manager,
                    pipeline_coordinator=coordinator,
                )
                service_registry.register("command_receiver", cmd_receiver)

            # Construct EngineContext
            self._context = EngineContext(
                engine_id=snapshot.engine.engine_id,
                node_id=snapshot.engine.node_id,
                environment=snapshot.engine.mode,
                snapshot=snapshot,
                services=service_registry,
            )

            self._state = BootstrapState.READY
            logger.info(
                "EngineBootstrap: System initialized successfully (Engine ID: %s, Mode: %s, Pipelines: %d)",
                self._context.engine_id,
                snapshot.engine.mode,
                len(snapshot.pipelines),
            )
            return BootstrapResult(state=BootstrapState.READY, context=self._context)

        except ConfigValidationError as exc:
            err_msg = f"Configuration validation failed: {exc}"
            logger.error("EngineBootstrap FAILED: %s", err_msg)
            self._state = BootstrapState.FAILED
            return BootstrapResult(state=BootstrapState.FAILED, error_message=err_msg)

        except Exception as exc:
            err_msg = f"Unexpected startup error: {exc}"
            logger.error("EngineBootstrap FAILED: %s", err_msg, exc_info=True)
            self._state = BootstrapState.FAILED
            return BootstrapResult(state=BootstrapState.FAILED, error_message=err_msg)

    def _validate_snapshot(self, snapshot: ConfigurationSnapshot) -> None:
        """Validate root configuration snapshot integrity."""
        if not snapshot.engine.engine_id:
            raise ConfigValidationError("Engine configuration missing engine_id.")

        if len(snapshot.pipelines) == 0:
            raise ConfigValidationError("ConfigurationSnapshot must contain at least one PipelineConfiguration.")

    def _build_camera_catalog(self, snapshot: ConfigurationSnapshot) -> CameraCatalog:
        """Construct CameraCatalog domain repository from snapshot pipelines."""
        catalog = CameraCatalog()
        for pipe in snapshot.pipelines:
            cam_cfg = pipe.app.camera
            source_cfg = pipe.app.source

            camera = Camera(
                camera_id=cam_cfg.camera_id,
                name=cam_cfg.name,
                source=source_cfg.uri,
                width=cam_cfg.resolution[0],
                height=cam_cfg.resolution[1],
                fps=cam_cfg.fps,
                status=CameraStatus.OFFLINE,
                raw_zones_payload=list(cam_cfg.raw_zones_payload),
            )
            for z in cam_cfg.zones:
                camera.add_zone(z)

            catalog.register_camera(camera)

        logger.info("EngineBootstrap: Built CameraCatalog with %d camera(s)", len(catalog))
        return catalog

    def _initialize_publishers(self, snapshot: ConfigurationSnapshot) -> CommunicationManager:
        """Instantiate and register publisher plugins with the CommunicationManager singleton."""
        comm_manager = CommunicationManager.get_instance()

        for pub_cfg in snapshot.publishers.publishers:
            if not pub_cfg.enabled:
                logger.info("EngineBootstrap: Publisher '%s' is disabled, skipping.", pub_cfg.name)
                continue

            try:
                # Instantiate publisher via PublisherRegistry plugin factory
                publisher_inst: EventPublisher = PublisherRegistry.create(
                    type_name=pub_cfg.publisher_type,
                    name=pub_cfg.name,
                    enabled=pub_cfg.enabled,
                    **pub_cfg.settings,
                )
                comm_manager.publisher_manager.register_publisher(publisher_inst)
                logger.info("EngineBootstrap: Registered publisher plugin '%s' (%s)", pub_cfg.name, pub_cfg.publisher_type)

            except KeyError as exc:
                logger.warning("EngineBootstrap: Publisher type notice: %s", exc)
            except Exception as exc:
                logger.error("EngineBootstrap: Failed to initialize publisher '%s': %s", pub_cfg.name, exc)

        return comm_manager
