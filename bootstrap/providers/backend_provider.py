"""
Backend REST Configuration Provider implementation.

Fetches live runtime camera configuration, RTSP endpoints, pipelines, and active analytics modules
directly from the ASP.NET Core Backend REST API endpoints (/api/v1/spatial/cameras & /api/v1/monitoring/overview).
"""

from __future__ import annotations

import logging
from typing import Any, Optional
import urllib.request
import json
import uuid

from camera_analytics.bootstrap.models import (
    ConfigurationSnapshot,
    EngineConfig,
    EngineRuntimeConfig,
    PipelineConfiguration,
    PublisherEntryConfig,
    PublishersConfig,
)
from camera_analytics.bootstrap.providers.base import ConfigurationProvider
from camera_analytics.config.schema import (
    AnalyticsConfig,
    AppConfig,
    CameraConfig,
    DetectorConfig,
    RunnerConfig,
    SourceConfig,
    TrackerConfig,
)
from camera_analytics.models.camera import Camera, CameraStatus

logger = logging.getLogger(__name__)


class BackendConfigurationProvider(ConfigurationProvider):
    """ConfigurationProvider requesting runtime camera assignments from ASP.NET Core Backend REST APIs."""

    def __init__(self, backend_url: str = "http://localhost:5100") -> None:
        self.backend_url = backend_url.rstrip("/")

    def load(self) -> ConfigurationSnapshot:
        """Fetch camera configuration and assigned modules from backend REST API and build ConfigurationSnapshot.

        Returns:
            Validated ConfigurationSnapshot populated with live backend camera & module assignments.
        """
        logger.info("[+] Requesting runtime bootstrap configuration from Backend API '%s/api/v1/engine/runtime/bootstrap'...", self.backend_url)

        bootstrap_data: dict[str, Any] = {}
        pipelines_raw: list[dict[str, Any]] = []

        try:
            req = urllib.request.Request(f"{self.backend_url}/api/v1/engine/runtime/bootstrap")
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    bootstrap_data = json.loads(resp.read().decode("utf-8"))
                    pipelines_raw = bootstrap_data.get("pipelines", [])
                    logger.info("[+] Successfully fetched bootstrap configuration for %d pipeline(s) from Backend API.", len(pipelines_raw))
        except Exception as exc:
            logger.warning("[!] Could not connect to Backend Bootstrap API at '%s/api/v1/engine/runtime/bootstrap': %s", self.backend_url, exc)

        pipeline_configs: list[PipelineConfiguration] = []

        # If backend returned bootstrap pipelines, process assigned camera(s) and modules
        if len(pipelines_raw) > 0:
            for target_pipe in pipelines_raw:
                cam_data = target_pipe.get("camera", {})
                camera_id = str(cam_data.get("cameraId", "c1"))
                camera_name = str(cam_data.get("name", "CAM-01 Main Lobby"))
                rtsp_url = str(cam_data.get("rtspUrl", "rtsp://admin:Admin1234@192.168.1.64/Streaming/channels/2"))
                pipeline_id = str(target_pipe.get("pipelineId", f"pipeline_{camera_id.replace('-', '_')}"))

                assigned_mods_raw = target_pipe.get("assignedModules", [])
                enabled_modules = [str(m.get("moduleCode")) for m in assigned_mods_raw if m.get("moduleCode")]

                if not enabled_modules:
                    enabled_modules = ["people_counting", "queue_detection", "loitering_detection"]

                raw_zones = cam_data.get("zones", [])
                logger.info("[+] Pipeline '%s' received %d live zone(s) from Backend for camera '%s'", pipeline_id, len(raw_zones), camera_id)

                cam_obj = Camera(
                    camera_id=camera_id,
                    name=camera_name,
                    source=rtsp_url,
                    width=1920,
                    height=1080,
                    fps=30.0,
                    status=CameraStatus.ONLINE,
                    description=f"RTSP stream from {camera_name}",
                )
                cam_obj.raw_zones_payload = raw_zones

                app_cfg = AppConfig(
                    camera=CameraConfig(
                        camera_id=camera_id,
                        name=camera_name,
                        resolution=(1920, 1080),
                        fps=30,
                        raw_zones_payload=tuple(raw_zones),
                    ),
                    source=SourceConfig(source_type="rtsp", uri=rtsp_url, params={"reconnect_attempts": 5, "reconnect_delay": 2.0}),
                    detector=DetectorConfig(model_name="yolo_pose", confidence_threshold=0.6, device="cuda:0"),
                    tracker=TrackerConfig(tracker_name="botsort", max_distance=120.0),
                    runner=RunnerConfig(process_every_n=1, max_frames=None),
                    analytics=AnalyticsConfig(enabled_modules=enabled_modules),
                )

                pipe_cfg = PipelineConfiguration(
                    pipeline_id=pipeline_id,
                    camera_id=camera_id,
                    app=app_cfg,
                    gpu_id=0,
                    enabled=True,
                )
                pipeline_configs.append(pipe_cfg)
        else:
            # Fallback default camera configuration when backend API is starting up
            fallback_cam_id = "cam_01_default"
            fallback_rtsp = "rtsp://admin:Admin1234@192.168.1.64/Streaming/channels/2"
            cam_obj = Camera(
                camera_id=fallback_cam_id,
                name="Default RTSP Camera",
                source=fallback_rtsp,
                width=1920,
                height=1080,
                fps=30.0,
                status=CameraStatus.ONLINE,
            )
            app_cfg = AppConfig(
                camera=CameraConfig(camera_id=fallback_cam_id, name="Default RTSP Camera"),
                source=SourceConfig(source_type="rtsp", uri=fallback_rtsp),
                detector=DetectorConfig(model_name="yolo_pose"),
                tracker=TrackerConfig(tracker_name="botsort"),
                runner=RunnerConfig(),
                analytics=AnalyticsConfig(enabled_modules=["people_counting"]),
            )
            pipe_cfg = PipelineConfiguration(
                pipeline_id="pipeline_default",
                camera_id=fallback_cam_id,
                app=app_cfg,
                gpu_id=0,
                enabled=True,
            )
            pipeline_configs.append(pipe_cfg)

        engine_cfg = EngineConfig(
            engine_id="engine_edge_01",
            node_id=str(uuid.uuid5(uuid.NAMESPACE_DNS, "engine_edge_01")),
            hostname="engine_edge_host",
            mode="enterprise",
        )

        publishers_cfg = PublishersConfig(
            publishers=(
                PublisherEntryConfig(
                    publisher_type="rabbitmq",
                    name="rabbitmq_events",
                    enabled=True,
                    settings={"host": "localhost", "port": 5672, "vhost": "cctv_vhost", "username": "cctv_admin", "password": "SecureCctvPass123"},
                ),
            )
        )

        runtime_cfg = EngineRuntimeConfig(
            plugin_directory="camera_analytics/plugins",
            diagnostics_enabled=True,
            max_module_latency_ms=100.0,
        )

        return ConfigurationSnapshot(
            engine=engine_cfg,
            pipelines=pipeline_configs,
            publishers=publishers_cfg,
            runtime=runtime_cfg,
        )
