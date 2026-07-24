"""
Configuration loader and validator.

Parses raw Python dictionary structures, validates required fields, types, and ranges,
and constructs strongly-typed AppConfig instances.
"""

from __future__ import annotations

import logging
from typing import Any

from camera_analytics.config.schema import (
    AnalyticsConfig,
    AppConfig,
    CameraConfig,
    DetectorConfig,
    RunnerConfig,
    SourceConfig,
    TrackerConfig,
)
from camera_analytics.models.zone import Zone

logger = logging.getLogger(__name__)


class ConfigValidationError(ValueError):
    """Raised when configuration validation fails."""


class ConfigLoader:
    """Loader and validator for converting dictionary inputs into typed AppConfig objects.

    Example::

        raw_dict = {
            "camera": {"camera_id": "cam_01", "name": "Main Gate"},
            "source": {"source_type": "rtsp", "uri": "rtsp://192.168.1.50/stream"},
            "detector": {"model_name": "yolo_pose", "confidence_threshold": 0.6},
            "tracker": {"tracker_name": "botsort", "max_distance": 120.0},
            "runner": {"process_every_n": 1, "max_frames": 100},
            "analytics": {
                "enabled_modules": ["people_analytics"],
                "module_settings": {"people_analytics": {"crowd_threshold": 5}},
            },
        }

        config = ConfigLoader.from_dict(raw_dict)
    """

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AppConfig:
        """Parse dictionary data and construct a validated AppConfig object.

        Args:
            data: Root configuration dictionary.

        Returns:
            Validated AppConfig instance.

        Raises:
            ConfigValidationError: If required fields are missing or values fail validation.
        """
        if not isinstance(data, dict):
            raise ConfigValidationError("Root configuration must be a dictionary.")

        camera_cfg = cls._load_camera(data.get("camera", {}))
        source_cfg = cls._load_source(data.get("source", {}))
        detector_cfg = cls._load_detector(data.get("detector", {}))
        tracker_cfg = cls._load_tracker(data.get("tracker", {}))
        runner_cfg = cls._load_runner(data.get("runner", {}))
        analytics_cfg = cls._load_analytics(data.get("analytics", {}))

        return AppConfig(
            camera=camera_cfg,
            source=source_cfg,
            detector=detector_cfg,
            tracker=tracker_cfg,
            runner=runner_cfg,
            analytics=analytics_cfg,
        )

    @classmethod
    def _load_camera(cls, data: dict[str, Any]) -> CameraConfig:
        """Validate and construct CameraConfig."""
        if not isinstance(data, dict):
            raise ConfigValidationError("'camera' configuration section must be a dictionary.")

        camera_id = data.get("camera_id")
        if not camera_id or not isinstance(camera_id, str):
            raise ConfigValidationError("'camera.camera_id' is required and must be a non-empty string.")

        name = str(data.get("name", ""))

        resolution_raw = data.get("resolution", (1920, 1080))
        if (
            not isinstance(resolution_raw, (list, tuple))
            or len(resolution_raw) != 2
            or not all(isinstance(v, int) and v > 0 for v in resolution_raw)
        ):
            raise ConfigValidationError("'camera.resolution' must be a tuple of 2 positive integers (width, height).")
        resolution = (int(resolution_raw[0]), int(resolution_raw[1]))

        fps = float(data.get("fps", 30.0))
        if fps <= 0:
            raise ConfigValidationError("'camera.fps' must be greater than 0.")

        zones_raw = data.get("zones", ())
        zones_list: list[Zone] = []
        if isinstance(zones_raw, (list, tuple)):
            for z in zones_raw:
                if isinstance(z, Zone):
                    zones_list.append(z)
                else:
                    raise ConfigValidationError("Items in 'camera.zones' must be Zone instances.")
        else:
            raise ConfigValidationError("'camera.zones' must be a list or tuple of Zone objects.")

        return CameraConfig(
            camera_id=camera_id,
            name=name,
            resolution=resolution,
            fps=fps,
            zones=tuple(zones_list),
        )

    @classmethod
    def _load_source(cls, data: dict[str, Any]) -> SourceConfig:
        """Validate and construct SourceConfig."""
        if not isinstance(data, dict):
            raise ConfigValidationError("'source' configuration section must be a dictionary.")

        source_type = data.get("source_type")
        if not source_type or not isinstance(source_type, str):
            raise ConfigValidationError("'source.source_type' is required (e.g. 'video', 'rtsp', 'usb', 'folder').")

        uri = data.get("uri")
        if uri is None or not isinstance(uri, (str, int)):
            raise ConfigValidationError("'source.uri' is required.")
        uri_str = str(uri)

        params = data.get("params", {})
        if not isinstance(params, dict):
            raise ConfigValidationError("'source.params' must be a dictionary.")

        return SourceConfig(
            source_type=source_type,
            uri=uri_str,
            params=dict(params),
        )

    @classmethod
    def _load_detector(cls, data: dict[str, Any]) -> DetectorConfig:
        """Validate and construct DetectorConfig."""
        if not isinstance(data, dict):
            raise ConfigValidationError("'detector' configuration section must be a dictionary.")

        model_name = str(data.get("model_name", "fake_detector"))
        model_path = str(data.get("model_path", ""))
        device = str(data.get("device", "cpu"))

        conf = float(data.get("confidence_threshold", 0.5))
        if not (0.0 <= conf <= 1.0):
            raise ConfigValidationError("'detector.confidence_threshold' must be between 0.0 and 1.0.")

        iou = float(data.get("iou_threshold", 0.45))
        if not (0.0 <= iou <= 1.0):
            raise ConfigValidationError("'detector.iou_threshold' must be between 0.0 and 1.0.")

        extra_params = data.get("extra_params", {})
        if not isinstance(extra_params, dict):
            raise ConfigValidationError("'detector.extra_params' must be a dictionary.")

        return DetectorConfig(
            model_name=model_name,
            model_path=model_path,
            device=device,
            confidence_threshold=conf,
            iou_threshold=iou,
            extra_params=dict(extra_params),
        )

    @classmethod
    def _load_tracker(cls, data: dict[str, Any]) -> TrackerConfig:
        """Validate and construct TrackerConfig."""
        if not isinstance(data, dict):
            raise ConfigValidationError("'tracker' configuration section must be a dictionary.")

        tracker_name = str(data.get("tracker_name", "fake_tracker"))

        max_distance = float(data.get("max_distance", 150.0))
        if max_distance <= 0:
            raise ConfigValidationError("'tracker.max_distance' must be greater than 0.")

        max_lost = int(data.get("max_lost", 10))
        if max_lost < 0:
            raise ConfigValidationError("'tracker.max_lost' must be 0 or greater.")

        extra_params = data.get("extra_params", {})
        if not isinstance(extra_params, dict):
            raise ConfigValidationError("'tracker.extra_params' must be a dictionary.")

        return TrackerConfig(
            tracker_name=tracker_name,
            max_distance=max_distance,
            max_lost=max_lost,
            extra_params=dict(extra_params),
        )

    @classmethod
    def _load_runner(cls, data: dict[str, Any]) -> RunnerConfig:
        """Validate and construct RunnerConfig."""
        if not isinstance(data, dict):
            raise ConfigValidationError("'runner' configuration section must be a dictionary.")

        process_every_n = int(data.get("process_every_n", 1))
        if process_every_n < 1:
            raise ConfigValidationError("'runner.process_every_n' must be 1 or greater.")

        max_frames_raw = data.get("max_frames")
        max_frames = int(max_frames_raw) if max_frames_raw is not None else None
        if max_frames is not None and max_frames <= 0:
            raise ConfigValidationError("'runner.max_frames' must be greater than 0 if specified.")

        return RunnerConfig(
            process_every_n=process_every_n,
            max_frames=max_frames,
        )

    @classmethod
    def _load_analytics(cls, data: dict[str, Any]) -> AnalyticsConfig:
        """Validate and construct AnalyticsConfig."""
        if not isinstance(data, dict):
            raise ConfigValidationError("'analytics' configuration section must be a dictionary.")

        enabled_raw = data.get("enabled_modules", ())
        if not isinstance(enabled_raw, (list, tuple)):
            raise ConfigValidationError("'analytics.enabled_modules' must be a list or tuple of module names.")
        enabled_modules = tuple(str(m) for m in enabled_raw)

        module_settings_raw = data.get("module_settings", {})
        if not isinstance(module_settings_raw, dict):
            raise ConfigValidationError("'analytics.module_settings' must be a dictionary.")

        module_settings: dict[str, dict[str, Any]] = {}
        for mod_name, settings in module_settings_raw.items():
            if not isinstance(settings, dict):
                raise ConfigValidationError(f"'analytics.module_settings.{mod_name}' must be a dictionary.")
            module_settings[str(mod_name)] = dict(settings)

        return AnalyticsConfig(
            enabled_modules=enabled_modules,
            module_settings=module_settings,
        )
