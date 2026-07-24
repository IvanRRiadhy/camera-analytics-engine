"""
Configuration management.

Provides a hierarchical, type-safe configuration system for the framework.
Supports loading from YAML files, merging multiple config sources,
and per-module configuration sections.
"""

from __future__ import annotations

import copy
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, TypeVar, overload

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ConfigError(Exception):
    """Raised when a configuration value is missing or invalid."""


@dataclass(slots=True)
class ModuleConfig:
    """Configuration section for a single analytics module.

    Each analytics module receives its own ModuleConfig containing
    module-specific settings extracted from the global config.

    Attributes:
        module_name: Name of the module this config belongs to.
        enabled: Whether the module should be active.
        settings: Flat key-value dictionary of module settings.
    """

    module_name: str
    enabled: bool = True
    settings: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: T = None) -> Any | T:
        """Get a setting value by key with an optional default.

        Args:
            key: Setting key to look up.
            default: Value to return if key is not found.

        Returns:
            The setting value, or the default.
        """
        return self.settings.get(key, default)

    def get_required(self, key: str) -> Any:
        """Get a required setting value. Raises if not found.

        Args:
            key: Setting key to look up.

        Returns:
            The setting value.

        Raises:
            ConfigError: If the key is not found.
        """
        if key not in self.settings:
            raise ConfigError(
                f"Required config key '{key}' not found "
                f"in module '{self.module_name}'."
            )
        return self.settings[key]

    def get_int(self, key: str, default: int = 0) -> int:
        """Get a setting as integer.

        Args:
            key: Setting key.
            default: Default value if not found.

        Returns:
            The integer value.
        """
        return int(self.settings.get(key, default))

    def get_float(self, key: str, default: float = 0.0) -> float:
        """Get a setting as float.

        Args:
            key: Setting key.
            default: Default value if not found.

        Returns:
            The float value.
        """
        return float(self.settings.get(key, default))

    def get_bool(self, key: str, default: bool = False) -> bool:
        """Get a setting as boolean.

        Args:
            key: Setting key.
            default: Default value if not found.

        Returns:
            The boolean value.
        """
        value = self.settings.get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("true", "1", "yes")
        return bool(value)

    def get_str(self, key: str, default: str = "") -> str:
        """Get a setting as string.

        Args:
            key: Setting key.
            default: Default value if not found.

        Returns:
            The string value.
        """
        return str(self.settings.get(key, default))


class Config:
    """Global configuration container for the entire framework.

    Manages a nested dictionary of configuration values and provides
    methods to extract per-module config sections, load from files,
    and merge multiple sources.

    Configuration structure convention::

        {
            "pipeline": {
                "process_every_n": 1,
                "log_level": "INFO"
            },
            "camera": {
                "source": "rtsp://...",
                "camera_id": "cam_01"
            },
            "modules": {
                "people_analytics": {
                    "enabled": true,
                    "confidence_threshold": 0.5,
                    "max_track_age": 30
                },
                "ppe_analytics": {
                    "enabled": false,
                    "classes": ["helmet", "vest"]
                }
            }
        }

    Example usage::

        config = Config.from_dict({
            "pipeline": {"log_level": "DEBUG"},
            "modules": {
                "people_analytics": {
                    "enabled": True,
                    "confidence_threshold": 0.6,
                }
            }
        })

        # Get pipeline-level setting
        level = config.get("pipeline.log_level", "INFO")

        # Get module-specific config
        mod_cfg = config.get_module_config("people_analytics")
        threshold = mod_cfg.get_float("confidence_threshold", 0.5)
    """

    def __init__(self, data: Optional[dict[str, Any]] = None) -> None:
        self._data: dict[str, Any] = data if data is not None else {}

    # --- Factory Methods ---

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Config:
        """Create a Config from a dictionary.

        Args:
            data: Configuration dictionary.

        Returns:
            A new Config instance.
        """
        return cls(data=copy.deepcopy(data))

    @classmethod
    def from_json_file(cls, path: str | Path) -> Config:
        """Load configuration from a JSON file.

        Args:
            path: Path to the JSON configuration file.

        Returns:
            A new Config instance.

        Raises:
            FileNotFoundError: If the file does not exist.
            json.JSONDecodeError: If the file is not valid JSON.
        """
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"Config file not found: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        logger.info("Loaded config from %s", file_path)
        return cls(data=data)

    @classmethod
    def from_yaml_file(cls, path: str | Path) -> Config:
        """Load configuration from a YAML file.

        Requires PyYAML to be installed. Falls back to a clear error
        message if not available.

        Args:
            path: Path to the YAML configuration file.

        Returns:
            A new Config instance.

        Raises:
            FileNotFoundError: If the file does not exist.
            ImportError: If PyYAML is not installed.
        """
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"Config file not found: {file_path}")

        try:
            import yaml
        except ImportError as exc:
            raise ImportError(
                "PyYAML is required to load YAML configs. "
                "Install with: pip install pyyaml"
            ) from exc

        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        logger.info("Loaded config from %s", file_path)
        return cls(data=data if data is not None else {})

    # --- Value Access ---

    def get(self, dotted_key: str, default: T = None) -> Any | T:
        """Get a value using dot-notation for nested access.

        Args:
            dotted_key: Dot-separated key path (e.g., 'pipeline.log_level').
            default: Value to return if not found.

        Returns:
            The config value, or the default.

        Example::

            config.get("pipeline.log_level", "INFO")
            config.get("modules.people_analytics.enabled", True)
        """
        keys = dotted_key.split(".")
        current: Any = self._data

        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default

        return current

    def set(self, dotted_key: str, value: Any) -> None:
        """Set a value using dot-notation, creating intermediate dicts.

        Args:
            dotted_key: Dot-separated key path.
            value: The value to set.

        Example::

            config.set("modules.people_analytics.confidence_threshold", 0.7)
        """
        keys = dotted_key.split(".")
        current = self._data

        for key in keys[:-1]:
            if key not in current or not isinstance(current[key], dict):
                current[key] = {}
            current = current[key]

        current[keys[-1]] = value

    # --- Module Config ---

    def get_module_config(self, module_name: str) -> ModuleConfig:
        """Extract configuration for a specific analytics module.

        Looks under the 'modules.<module_name>' section. If the section
        does not exist, returns a default ModuleConfig with enabled=True.

        Args:
            module_name: Name of the module (must match key in config).

        Returns:
            A ModuleConfig instance for the module.
        """
        modules_section = self._data.get("modules", {})
        module_data = modules_section.get(module_name, {})

        enabled = module_data.pop("enabled", True) if module_data else True
        settings = copy.deepcopy(module_data)

        return ModuleConfig(
            module_name=module_name,
            enabled=enabled,
            settings=settings,
        )

    # --- Merging ---

    def merge(self, other: Config) -> None:
        """Merge another Config into this one (deep merge).

        Values from `other` take precedence over existing values.
        Nested dictionaries are merged recursively.

        Args:
            other: The Config to merge in.
        """
        self._data = self._deep_merge(self._data, other._data)

    @staticmethod
    def _deep_merge(
        base: dict[str, Any], override: dict[str, Any]
    ) -> dict[str, Any]:
        """Recursively merge two dictionaries.

        Args:
            base: The base dictionary.
            override: The dictionary whose values take precedence.

        Returns:
            A new merged dictionary.
        """
        result = copy.deepcopy(base)
        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = Config._deep_merge(result[key], value)
            else:
                result[key] = copy.deepcopy(value)
        return result

    # --- Utility ---

    def to_dict(self) -> dict[str, Any]:
        """Export the full configuration as a plain dictionary.

        Returns:
            Deep copy of the internal config data.
        """
        return copy.deepcopy(self._data)

    def __repr__(self) -> str:
        return f"Config(keys={list(self._data.keys())})"
