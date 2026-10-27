"""
Standalone Configuration Provider Implementation.

Loads, validates, and constructs immutable `ConfigurationSnapshot` objects directly from local JSON
configuration files (e.g. `configs/standalone.json`) without requiring any connection to ASP.NET Core Backend.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

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
from camera_analytics.config.validator import StandaloneConfigValidator
from camera_analytics.models.camera import Camera, CameraStatus
from camera_analytics.models.zone import Point, Zone, ZoneType

logger = logging.getLogger(__name__)


class StandaloneConfigurationProvider(ConfigurationProvider):
    """ConfigurationProvider loading local JSON configuration files for Standalone Mode."""

    def __init__(self, config_file_path: str = "configs/standalone.json") -> None:
        from camera_analytics.bootstrap.resource_manager import RuntimeResourceManager
        rm = RuntimeResourceManager.get_instance()
        self._config_file_path = rm.resolve_config_path(config_file_path)

    def load(self) -> ConfigurationSnapshot:
        """Load and parse local configuration file into ConfigurationSnapshot."""
        if not self._config_file_path.exists():
            from camera_analytics.bootstrap.resource_manager import RuntimeResourceManager
            rm = RuntimeResourceManager.get_instance()
            fallback_paths = [rm.resolve_config_path("configs/production.json"), rm.resolve_config_path("configs/sample_runtime.json")]
            for f_path in fallback_paths:
                if f_path.exists():
                    self._config_file_path = f_path
                    break

        if not self._config_file_path.exists():
            logger.warning("StandaloneConfigurationProvider: Configuration file '%s' not found. Using default empty snapshot.", self._config_file_path)
            return self._build_empty_snapshot()

        logger.info("StandaloneConfigurationProvider: Loading standalone configuration from '%s'", self._config_file_path)
        with open(self._config_file_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        # Validate configuration structure fast-failing on errors
        StandaloneConfigValidator.validate(raw_data)

        return self.parse_dict(raw_data)

    def parse_dict(self, raw_data: Dict[str, Any]) -> ConfigurationSnapshot:
        """Parse raw dictionary into a strongly typed ConfigurationSnapshot."""
        engine_dict = raw_data.get("engine", {})
        runtime_dict = raw_data.get("runtime", {})
        comm_dict = raw_data.get("communication", {})
        cameras_list = raw_data.get("cameras", [])

        # Version Metadata
        schema_version = raw_data.get("schema_version", "2.0.0")

        # 1. Engine Configuration
        engine_cfg = EngineConfig(
            engine_id=engine_dict.get("engine_id", "engine_standalone_01"),
            node_id=engine_dict.get("node_id", "standalone_node"),
            hostname=engine_dict.get("hostname", "localhost"),
            mode="standalone",
            log_level=engine_dict.get("log_level", "INFO"),
            schema_version=schema_version,
        )

        # 2. Runtime Configuration
        runtime_cfg = EngineRuntimeConfig(
            plugin_directory="camera_analytics/plugins",
            diagnostics_enabled=bool(runtime_dict.get("diagnostics_enabled", True)),
            max_module_latency_ms=float(runtime_dict.get("max_module_latency_ms", 100.0)),
            schema_version=schema_version,
        )

        # 3. Communication Publishers Configuration
        raw_pubs = comm_dict.get("publishers", ["console", "log"])
        pub_entries = []
        for pub in raw_pubs:
            if isinstance(pub, str):
                pub_entries.append(PublisherEntryConfig(publisher_type=pub, name=pub, enabled=True))
            elif isinstance(pub, dict):
                p_type = pub.get("type", "console")
                pub_entries.append(PublisherEntryConfig(
                    publisher_type=p_type,
                    name=pub.get("name", p_type),
                    enabled=pub.get("enabled", True),
                    settings={k: v for k, v in pub.items() if k not in ["type", "enabled", "name"]}
                ))

        publishers_cfg = PublishersConfig(
            publishers=tuple(pub_entries),
            schema_version=schema_version,
        )

        # 4. Cameras, Zones & Pipelines Construction
        cameras_map: Dict[str, Camera] = {}
        pipeline_configs: Dict[str, PipelineConfiguration] = {}

        # Module settings (top-level or per-camera)
        global_module_settings = raw_data.get("module_settings", {})
        if not isinstance(global_module_settings, dict):
            global_module_settings = {}

        for cam_data in cameras_list:
            cam_id = cam_data.get("camera_id", "cam_default")
            cam_name = cam_data.get("name", f"Camera {cam_id}")

            src_val = cam_data.get("source")
            rtsp_val = cam_data.get("rtsp_url")
            if src_val is not None and rtsp_val is not None and str(src_val) != str(rtsp_val):
                logger.warning(
                    "StandaloneConfigurationProvider: Camera '%s' defines both 'source' ('%s') and 'rtsp_url' ('%s') with conflicting values. Precedence order: 'source' > 'rtsp_url' > '0'. Using 'source'.",
                    cam_id, src_val, rtsp_val
                )

            rtsp_url = src_val if src_val is not None else (rtsp_val if rtsp_val is not None else "0")
            fps = float(cam_data.get("fps", 30.0))
            device = cam_data.get("device", "cuda:0")

            # Parse Zones for this camera
            zones_dict: Dict[str, Zone] = {}
            for z_raw in cam_data.get("zones", []):
                z_id = z_raw.get("zone_id", "z_default")
                z_name = z_raw.get("name", z_id)
                z_type_str = str(z_raw.get("type", z_raw.get("zone_type", "REGION"))).upper()
                if z_type_str == "POLYGON":
                    z_type_str = "REGION"
                z_type = ZoneType[z_type_str] if z_type_str in ZoneType.__members__ else ZoneType.REGION

                pts = [Point(x=int(p[0]), y=int(p[1])) for p in z_raw.get("points", [])]
                color = tuple(z_raw.get("color", [0, 255, 0]))

                zone_obj = Zone(
                    zone_id=z_id,
                    name=z_name,
                    zone_type=z_type,
                    points=pts,
                    color=color,
                    metadata=z_raw.get("metadata", {}),
                )
                zones_dict[z_id] = zone_obj

            # Construct Camera Entity with Zones
            camera_obj = Camera(
                camera_id=cam_id,
                name=cam_name,
                source=rtsp_url,
                fps=fps,
                zones=zones_dict,
                raw_zones_payload=cam_data.get("zones", []),
                status=CameraStatus.ONLINE,
            )
            cameras_map[cam_id] = camera_obj

            cam_module_settings = dict(global_module_settings)
            if isinstance(cam_data.get("module_settings"), dict):
                cam_module_settings.update(cam_data["module_settings"])

            # Construct Pipeline Configuration for this Camera
            app_cfg = AppConfig(
                camera=CameraConfig(
                    camera_id=cam_id,
                    name=cam_name,
                    fps=fps,
                    zones=tuple(zones_dict.values()),
                    raw_zones_payload=tuple(cam_data.get("zones", [])),
                ),
                source=SourceConfig(source_type="rtsp", uri=rtsp_url),
                detector=DetectorConfig(device=device),
                tracker=TrackerConfig(),
                analytics=AnalyticsConfig(
                    enabled_modules=tuple(cam_data.get("enabled_modules", ["people_counting", "queue_detection", "loitering_detection"])),
                    module_settings=cam_module_settings,
                ),
                runner=RunnerConfig(),
            )

            pipe_cfg = PipelineConfiguration(
                pipeline_id=f"pipeline_{cam_id}",
                camera_id=cam_id,
                app=app_cfg,
                gpu_id=0,
                enabled=True,
            )
            pipeline_configs[cam_id] = pipe_cfg

        return ConfigurationSnapshot(
            schema_version=schema_version,
            engine=engine_cfg,
            runtime=runtime_cfg,
            publishers=publishers_cfg,
            pipelines=tuple(pipeline_configs.values()),
        )

    def _build_empty_snapshot(self) -> ConfigurationSnapshot:
        return ConfigurationSnapshot(
            schema_version="2.0.0",
            engine=EngineConfig(engine_id="standalone_01", mode="standalone"),
            runtime=EngineRuntimeConfig(),
            publishers=PublishersConfig(publishers=(PublisherEntryConfig(publisher_type="console"),)),
            pipelines=(),
        )
