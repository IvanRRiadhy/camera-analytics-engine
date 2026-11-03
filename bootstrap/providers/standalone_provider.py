"""
Standalone Configuration Provider Implementation.

Loads, validates, and constructs immutable `ConfigurationSnapshot` objects directly from local JSON
configuration files (e.g. `configs/standalone.json`) without requiring any connection to ASP.NET Core Backend.
"""

from __future__ import annotations

import importlib.util
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
from camera_analytics.config.env_expander import expand_env_vars
from camera_analytics.config.identity import resolve_application_id
from camera_analytics.config.schema import (
    AnalyticsConfig,
    AppConfig,
    CameraConfig,
    DetectorConfig,
    IngestionConfig,
    RunnerConfig,
    SourceConfig,
    TrackerConfig,
)
from camera_analytics.config.validator import StandaloneConfigValidator
from camera_analytics.models.camera import Camera, CameraStatus
from camera_analytics.models.zone import Point, Zone, ZoneType
from camera_analytics.utils.url_sanitizer import redact_rtsp_url

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

        raw_data = expand_env_vars(raw_data)

        # Validate configuration structure fast-failing on errors
        StandaloneConfigValidator.validate(raw_data)

        return self.parse_dict(raw_data, expand=False)

    def parse_dict(self, raw_data: Dict[str, Any], expand: bool = True) -> ConfigurationSnapshot:
        """Parse raw dictionary into a strongly typed ConfigurationSnapshot."""
        if expand:
            raw_data = expand_env_vars(raw_data)
        StandaloneConfigValidator.validate_messaging(raw_data)

        engine_dict = raw_data.get("engine", {})
        runtime_dict = raw_data.get("runtime", {})
        comm_dict = raw_data.get("communication", {})
        cameras_list = raw_data.get("cameras", [])

        # Version Metadata
        schema_version = raw_data.get("schema_version", "2.0.0")

        app_id = resolve_application_id(config=raw_data, mode="standalone")

        # 1. Engine Configuration
        engine_cfg = EngineConfig(
            engine_id=engine_dict.get("engine_id", "engine_standalone_01"),
            node_id=engine_dict.get("node_id", "standalone_node"),
            hostname=engine_dict.get("hostname", "localhost"),
            mode="standalone",
            log_level=engine_dict.get("log_level", "INFO"),
            schema_version=schema_version,
            application_id=app_id,
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
            if not bool(cam_data.get("enabled", True)):
                logger.info(
                    "StandaloneConfigurationProvider: Skipping disabled camera '%s' (enabled=false).",
                    cam_id,
                )
                continue
            cam_name = cam_data.get("name", f"Camera {cam_id}")

            src_val = cam_data.get("source")
            rtsp_val = cam_data.get("rtsp_url")
            if src_val is not None and rtsp_val is not None and str(src_val) != str(rtsp_val):
                logger.warning(
                    "StandaloneConfigurationProvider: Camera '%s' defines both 'source' ('%s') and 'rtsp_url' ('%s') with conflicting values. Precedence order: 'source' > 'rtsp_url' > '0'. Using 'source'.",
                    cam_id, redact_rtsp_url(str(src_val)), redact_rtsp_url(str(rtsp_val))
                )

            rtsp_url = src_val if src_val is not None else (rtsp_val if rtsp_val is not None else "0")
            fps = float(cam_data.get("fps", 30.0))
            device = cam_data.get("device", "cuda:0")

            # Parse Zones for this camera
            zones_dict: Dict[str, Zone] = {}
            seen_zone_ids: set[str] = set()
            loaded_raw_zones: list[dict[str, Any]] = []

            for idx, z_raw in enumerate(cam_data.get("zones", [])):
                z_id = str(
                    z_raw.get("zone_id")
                    or z_raw.get("id")
                    or z_raw.get("zoneId")
                    or f"z_{len(zones_dict)}"
                )
                if z_id in seen_zone_ids:
                    logger.warning(
                        "StandaloneConfigurationProvider: Duplicate zone_id '%s' detected for camera '%s'. Skipping duplicate zone.",
                        z_id,
                        cam_id,
                    )
                    continue
                seen_zone_ids.add(z_id)

                z_raw_copy = dict(z_raw)
                z_raw_copy["zone_id"] = z_id
                loaded_raw_zones.append(z_raw_copy)

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
                raw_zones_payload=loaded_raw_zones,
                status=CameraStatus.ONLINE,
            )
            cameras_map[cam_id] = camera_obj

            cam_module_settings: Dict[str, Any] = {
                k: (dict(v) if isinstance(v, dict) else v)
                for k, v in global_module_settings.items()
            }
            analytics_dict = cam_data.get("analytics") if isinstance(cam_data.get("analytics"), dict) else {}

            has_top_ms = "module_settings" in cam_data and isinstance(cam_data.get("module_settings"), dict)
            has_ana_ms = "module_settings" in analytics_dict and isinstance(analytics_dict.get("module_settings"), dict)
            if has_top_ms and has_ana_ms and cam_data["module_settings"] != analytics_dict["module_settings"]:
                logger.warning(
                    "StandaloneConfigurationProvider: Camera '%s' defines conflicting 'module_settings' at camera top-level and 'analytics.module_settings'. Precedence: camera top-level > analytics.module_settings.",
                    cam_id,
                )
            if has_ana_ms:
                for k, v in analytics_dict["module_settings"].items():
                    if isinstance(v, dict) and isinstance(cam_module_settings.get(k), dict):
                        cam_module_settings[k] = {**cam_module_settings[k], **v}
                    else:
                        cam_module_settings[k] = dict(v) if isinstance(v, dict) else v
            if has_top_ms:
                for k, v in cam_data["module_settings"].items():
                    if isinstance(v, dict) and isinstance(cam_module_settings.get(k), dict):
                        cam_module_settings[k] = {**cam_module_settings[k], **v}
                    else:
                        cam_module_settings[k] = dict(v) if isinstance(v, dict) else v

            has_top_mods = "enabled_modules" in cam_data and isinstance(cam_data.get("enabled_modules"), list)
            has_ana_mods = "enabled_modules" in analytics_dict and isinstance(analytics_dict.get("enabled_modules"), list)
            if has_top_mods and has_ana_mods and cam_data["enabled_modules"] != analytics_dict["enabled_modules"]:
                logger.warning(
                    "StandaloneConfigurationProvider: Camera '%s' defines conflicting 'enabled_modules' at camera top-level (%s) and 'analytics.enabled_modules' (%s). Precedence: camera top-level > analytics.enabled_modules.",
                    cam_id,
                    cam_data["enabled_modules"],
                    analytics_dict["enabled_modules"],
                )

            if has_top_mods:
                raw_enabled_modules = list(cam_data["enabled_modules"])
                explicit_modules_key = True
            elif has_ana_mods:
                raw_enabled_modules = list(analytics_dict["enabled_modules"])
                explicit_modules_key = True
            else:
                raw_enabled_modules = ["people_counting", "queue_detection", "loitering_detection"]
                explicit_modules_key = False

            valid_enabled_modules: List[str] = []
            for mod_code in raw_enabled_modules:
                if not isinstance(mod_code, str) or not mod_code.strip():
                    logger.warning(
                        "StandaloneConfigurationProvider: Camera '%s' skipping invalid module code '%s'.",
                        cam_id,
                        mod_code,
                    )
                    continue

                module_target = f"camera_analytics.plugins.{mod_code}.plugin"
                is_valid = False
                find_err: Optional[str] = None
                try:
                    spec = importlib.util.find_spec(module_target)
                    is_valid = spec is not None
                except (ModuleNotFoundError, ImportError, ValueError) as exc:
                    is_valid = False
                    find_err = f" ({type(exc).__name__}: {exc})"

                if not is_valid:
                    logger.warning(
                        "StandaloneConfigurationProvider: Camera '%s' skipping unknown module code '%s'%s.",
                        cam_id,
                        mod_code,
                        find_err or "",
                    )
                    continue
                valid_enabled_modules.append(mod_code)

            if len(valid_enabled_modules) == 0:
                logger.error(
                    "StandaloneConfigurationProvider: Camera '%s' has no valid enabled_modules (%s). Skipping pipeline creation.",
                    cam_id,
                    raw_enabled_modules,
                )
                continue

            resolved_enabled_modules = tuple(valid_enabled_modules)

            open_timeout_sec = float(
                cam_data.get(
                    "open_timeout_sec",
                    cam_data.get(
                        "rtsp_open_timeout_sec",
                        cam_data.get("connect_timeout_sec", 5.0),
                    ),
                )
            )
            read_timeout_sec = float(
                cam_data.get(
                    "read_timeout_sec",
                    cam_data.get("rtsp_read_timeout_sec", 5.0),
                )
            )
            source_params: Dict[str, Any] = {
                "open_timeout_sec": open_timeout_sec,
                "read_timeout_sec": read_timeout_sec,
            }
            if "tcp_precheck_timeout_sec" in cam_data:
                source_params["tcp_precheck_timeout_sec"] = float(cam_data["tcp_precheck_timeout_sec"])

            # Construct Pipeline Configuration for this Camera
            ingestion_dict = cam_data.get("ingestion") if isinstance(cam_data.get("ingestion"), dict) else (
                raw_data.get("ingestion") if isinstance(raw_data.get("ingestion"), dict) else {}
            )
            ingestion_cfg = IngestionConfig(
                overflow_policy=str(ingestion_dict.get("overflow_policy", "auto")).lower(),
                queue_capacity=int(ingestion_dict.get("queue_capacity", 30)),
                buffer_capacity=int(ingestion_dict.get("buffer_capacity", 30)),
            )

            app_cfg = AppConfig(
                camera=CameraConfig(
                    camera_id=cam_id,
                    name=cam_name,
                    fps=fps,
                    zones=tuple(zones_dict.values()),
                    raw_zones_payload=tuple(loaded_raw_zones),
                ),
                source=SourceConfig(source_type="rtsp", uri=rtsp_url, params=source_params),
                detector=DetectorConfig(device=device),
                tracker=TrackerConfig(),
                analytics=AnalyticsConfig(
                    enabled_modules=resolved_enabled_modules,
                    module_settings=cam_module_settings,
                ),
                runner=RunnerConfig(),
                ingestion=ingestion_cfg,
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
            messaging=raw_data.get("messaging"),
        )

    def _build_empty_snapshot(self) -> ConfigurationSnapshot:
        return ConfigurationSnapshot(
            schema_version="2.0.0",
            engine=EngineConfig(engine_id="standalone_01", mode="standalone"),
            runtime=EngineRuntimeConfig(),
            publishers=PublishersConfig(publishers=(PublisherEntryConfig(publisher_type="console"),)),
            pipelines=(),
        )
