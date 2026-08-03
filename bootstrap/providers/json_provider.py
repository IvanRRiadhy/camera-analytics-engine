"""
JSON Configuration Provider implementation with Zone Deserialization & Schema Versioning support.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Union

from camera_analytics.bootstrap.models import (
    ConfigurationSnapshot,
    EngineConfig,
    EngineRuntimeConfig,
    PipelineConfiguration,
    PublisherEntryConfig,
    PublishersConfig,
)
from camera_analytics.bootstrap.providers.base import ConfigurationProvider
from camera_analytics.config.loader import ConfigLoader, ConfigValidationError
from camera_analytics.config.schema import AppConfig
from camera_analytics.models.zone import Point, Zone, ZoneType

logger = logging.getLogger(__name__)


class JsonConfigurationProvider(ConfigurationProvider):
    """ConfigurationProvider loading JSON files from a specified configuration directory.

    Parses, validates schema versions, deserializes Zone geometry objects, delegates
    subsystem validation to `ConfigLoader.from_dict()`, and builds an immutable
    `ConfigurationSnapshot`.
    """

    def __init__(self, config_dir: Union[str, Path] = "config") -> None:
        self._config_dir = Path(config_dir)

    def load(self) -> ConfigurationSnapshot:
        """Load JSON configuration files and construct ConfigurationSnapshot.

        Files loaded:
            - engine.json
            - cameras.json
            - zones.json
            - analytics.json
            - publishers.json
            - runtime.json

        Returns:
            Validated ConfigurationSnapshot instance.
        """
        if self._config_dir.is_file():
            raw_single = self._read_json_file(self._config_dir)
            raw_engine = raw_single.get("engine", raw_single)
            raw_cameras = raw_single
            raw_zones = raw_single
            raw_analytics = raw_single
            raw_publishers = raw_single
            raw_runtime = raw_single.get("runtime", raw_single)
        else:
            if not self._config_dir.exists() or not self._config_dir.is_dir():
                raise ConfigValidationError(
                    f"Configuration directory '{self._config_dir}' does not exist or is not a directory."
                )

            raw_engine = self._read_json("engine.json")
            raw_cameras = self._read_json("cameras.json")
            raw_zones = self._read_json("zones.json")
            raw_analytics = self._read_json("analytics.json")
            raw_publishers = self._read_json("publishers.json")
            raw_runtime = self._read_json("runtime.json")

        engine_cfg = self._build_engine_config(raw_engine)
        zones_by_camera = self._deserialize_and_group_zones(raw_zones)
        pipelines_cfg = self._build_pipelines_config(raw_cameras, zones_by_camera, raw_analytics)
        publishers_cfg = self._build_publishers_config(raw_publishers)
        runtime_cfg = self._build_runtime_config(raw_runtime)

        return ConfigurationSnapshot(
            schema_version=raw_engine.get("schema_version", "1.0.0"),
            engine=engine_cfg,
            pipelines=pipelines_cfg,
            publishers=publishers_cfg,
            runtime=runtime_cfg,
        )

    def _read_json_file(self, file_path: Path) -> dict[str, Any]:
        """Read and parse a single JSON file."""
        if not file_path.exists():
            raise ConfigValidationError(f"Required configuration file '{file_path}' was not found.")

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ConfigValidationError(f"Root of configuration file '{file_path.name}' must be a JSON object.")
            return data
        except json.JSONDecodeError as exc:
            raise ConfigValidationError(f"Failed to parse JSON file '{file_path.name}': {exc}") from exc

    def _read_json(self, filename: str) -> dict[str, Any]:
        """Read and parse a JSON file within config_dir."""
        return self._read_json_file(self._config_dir / filename)

    def _build_engine_config(self, raw: dict[str, Any]) -> EngineConfig:
        engine_id = raw.get("engine_id")
        if not engine_id or not isinstance(engine_id, str):
            raise ConfigValidationError("'engine.json' requires a non-empty string 'engine_id'.")

        return EngineConfig(
            engine_id=engine_id,
            node_id=str(raw.get("node_id", "")),
            hostname=str(raw.get("hostname", "")),
            mode=str(raw.get("mode", "standalone")),
            log_level=str(raw.get("log_level", "INFO")),
            schema_version=str(raw.get("schema_version", "1.0.0")),
        )

    def _deserialize_and_group_zones(self, raw: dict[str, Any]) -> dict[str, list[Zone]]:
        """Deserialize raw JSON zone objects into domain Zone instances grouped by camera_id."""
        zones_data = raw.get("zones", [])
        if not isinstance(zones_data, list):
            raise ConfigValidationError("'zones.json' field 'zones' must be a JSON array.")

        grouped: dict[str, list[Zone]] = {}

        for z in zones_data:
            if not isinstance(z, dict):
                raise ConfigValidationError("Items in 'zones.json' must be JSON objects.")

            camera_id = z.get("camera_id")
            if not camera_id or not isinstance(camera_id, str):
                raise ConfigValidationError("Zone entry missing required 'camera_id' string.")

            zone_id = z.get("zone_id")
            if not zone_id or not isinstance(zone_id, str):
                raise ConfigValidationError("Zone entry missing required 'zone_id' string.")

            name = str(z.get("name", zone_id))
            z_type_str = str(z.get("zone_type", "REGION")).upper()
            if z_type_str not in ZoneType.__members__:
                valid_types = ", ".join(ZoneType.__members__.keys())
                raise ConfigValidationError(
                    f"Zone '{zone_id}' invalid zone_type '{z_type_str}'. Must be one of [{valid_types}]."
                )
            zone_type = ZoneType[z_type_str]

            points_raw = z.get("points", [])
            if not isinstance(points_raw, list):
                raise ConfigValidationError(f"Zone '{zone_id}' 'points' must be a list of [x, y] coordinates.")

            points: list[Point] = []
            for p in points_raw:
                if not isinstance(p, (list, tuple)) or len(p) != 2 or not all(isinstance(v, int) for v in p):
                    raise ConfigValidationError(
                        f"Zone '{zone_id}' contains invalid point coordinate {p}. Must be [int, int]."
                    )
                points.append(Point(x=int(p[0]), y=int(p[1])))

            color_raw = z.get("color", [0, 255, 0])
            if (
                not isinstance(color_raw, (list, tuple))
                or len(color_raw) != 3
                or not all(isinstance(v, int) and 0 <= v <= 255 for v in color_raw)
            ):
                raise ConfigValidationError(f"Zone '{zone_id}' color must be [R, G, B] ints between 0-255.")
            color = (int(color_raw[0]), int(color_raw[1]), int(color_raw[2]))

            metadata = z.get("metadata", {})
            if not isinstance(metadata, dict):
                raise ConfigValidationError(f"Zone '{zone_id}' metadata must be an object.")

            zone_obj = Zone(
                zone_id=zone_id,
                name=name,
                zone_type=zone_type,
                points=points,
                color=color,
                metadata=dict(metadata),
            )

            grouped.setdefault(camera_id, []).append(zone_obj)

        return grouped

    def _build_pipelines_config(
        self,
        raw_cameras: dict[str, Any],
        zones_by_camera: dict[str, list[Zone]],
        raw_analytics: dict[str, Any],
    ) -> tuple[PipelineConfiguration, ...]:
        """Combine cameras, deserialized zones, and analytics settings into PipelineConfigurations."""
        cameras_list = raw_cameras.get("cameras", [])
        if not isinstance(cameras_list, list) or len(cameras_list) == 0:
            raise ConfigValidationError("'cameras.json' field 'cameras' must be a non-empty array.")

        pipelines: list[PipelineConfiguration] = []

        for cam in cameras_list:
            if not isinstance(cam, dict):
                raise ConfigValidationError("Items in 'cameras.json' must be JSON objects.")

            camera_id = cam.get("camera_id")
            if not camera_id or not isinstance(camera_id, str):
                raise ConfigValidationError("Camera entry missing required 'camera_id'.")

            # Attach deserialized Zone domain instances
            cam_copy = dict(cam)
            cam_copy["zones"] = zones_by_camera.get(camera_id, [])

            # Construct raw dictionary for ConfigLoader.from_dict()
            app_raw_dict = {
                "camera": cam_copy,
                "source": cam.get("source", {}),
                "detector": cam.get("detector", {}),
                "tracker": cam.get("tracker", {}),
                "runner": cam.get("runner", {}),
                "analytics": raw_analytics.get("analytics", {}),
            }

            # Delegate subsystem schema validation to ConfigLoader
            app_config: AppConfig = ConfigLoader.from_dict(app_raw_dict)

            pipeline_id = str(cam.get("pipeline_id", f"pipeline_{camera_id}"))
            gpu_id = int(cam.get("gpu_id", 0))
            enabled = bool(cam.get("enabled", True))

            pipelines.append(
                PipelineConfiguration(
                    pipeline_id=pipeline_id,
                    camera_id=camera_id,
                    app=app_config,
                    gpu_id=gpu_id,
                    enabled=enabled,
                )
            )

        return tuple(pipelines)

    def _build_publishers_config(self, raw: dict[str, Any]) -> PublishersConfig:
        publishers_raw = raw.get("publishers", [])
        if not isinstance(publishers_raw, list):
            raise ConfigValidationError("'publishers.json' field 'publishers' must be an array.")

        entries: list[PublisherEntryConfig] = []
        for pub in publishers_raw:
            if not isinstance(pub, dict):
                raise ConfigValidationError("Items in 'publishers.json' must be objects.")

            pub_type = pub.get("type")
            if not pub_type or not isinstance(pub_type, str):
                raise ConfigValidationError("Publisher entry missing required 'type' string.")

            name = str(pub.get("name", pub_type))
            enabled = bool(pub.get("enabled", True))
            settings = pub.get("settings", {})
            if not isinstance(settings, dict):
                raise ConfigValidationError(f"Publisher '{name}' settings must be an object.")

            entries.append(
                PublisherEntryConfig(
                    publisher_type=pub_type,
                    name=name,
                    enabled=enabled,
                    settings=dict(settings),
                )
            )

        return PublishersConfig(
            publishers=tuple(entries),
            schema_version=str(raw.get("schema_version", "1.0.0")),
        )

    def _build_runtime_config(self, raw: dict[str, Any]) -> EngineRuntimeConfig:
        plugin_dir = str(raw.get("plugin_directory", "camera_analytics/plugins"))
        diag_enabled = bool(raw.get("diagnostics_enabled", True))
        max_lat = float(raw.get("max_module_latency_ms", 100.0))

        return EngineRuntimeConfig(
            plugin_directory=plugin_dir,
            diagnostics_enabled=diag_enabled,
            max_module_latency_ms=max_lat,
            schema_version=str(raw.get("schema_version", "1.0.0")),
        )
