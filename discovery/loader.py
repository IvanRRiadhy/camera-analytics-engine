"""
Manifest Loader Component.

Provides ManifestLoader class for reading and validating JSON manifest files,
ensuring required manifest schema attributes are present before constructing PluginManifest objects.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Union

from camera_analytics.discovery.manifest import PluginManifest

logger = logging.getLogger(__name__)


class ManifestValidationError(ValueError):
    """Raised when a plugin manifest fails validation requirements."""


class ManifestLoader:
    """Loader parsing and validating plugin manifest JSON files into PluginManifest objects."""

    REQUIRED_FIELDS: tuple[str, ...] = ("plugin_id", "version", "sdk_version", "entry_point")

    def __init__(self) -> None:
        pass

    def load_from_file(self, manifest_path: Union[str, Path]) -> PluginManifest:
        """Load, parse, and validate a manifest JSON file.

        Args:
            manifest_path: Absolute or relative file path to manifest.json.

        Returns:
            PluginManifest instance.

        Raises:
            ManifestValidationError: If file does not exist, is invalid JSON, or lacks required fields.
        """
        path = Path(manifest_path)

        if not path.is_file():
            raise ManifestValidationError(f"Manifest file not found: {path}")

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as exc:
            raise ManifestValidationError(f"Invalid JSON syntax in manifest '{path}': {exc}") from exc
        except Exception as exc:
            raise ManifestValidationError(f"Failed to read manifest file '{path}': {exc}") from exc

        return self.load_from_dict(data, source_path=str(path))

    def load_from_dict(self, data: dict[str, Any], source_path: str = "<dict>") -> PluginManifest:
        """Validate raw dictionary data and construct PluginManifest instance.

        Args:
            data: Raw dictionary loaded from manifest JSON.
            source_path: Label or path source for error message context.

        Returns:
            PluginManifest instance.

        Raises:
            ManifestValidationError: If required fields are missing or invalid.
        """
        if not isinstance(data, dict):
            raise ManifestValidationError(f"Manifest content must be a JSON object, got {type(data).__name__} in '{source_path}'")

        missing: list[str] = []
        for field in self.REQUIRED_FIELDS:
            val = data.get(field)
            if val is None or (isinstance(val, str) and not val.strip()):
                missing.append(field)

        if missing:
            raise ManifestValidationError(
                f"Manifest validation failed for '{source_path}': Missing required fields {missing}"
            )

        try:
            return PluginManifest(
                plugin_id=str(data["plugin_id"]).strip(),
                name=str(data.get("name", data["plugin_id"])).strip(),
                version=str(data["version"]).strip(),
                sdk_version=str(data["sdk_version"]).strip(),
                entry_point=str(data["entry_point"]).strip(),
                author=str(data.get("author", "Enterprise Analytics Team")).strip(),
                description=str(data.get("description", "Analytics Plugin")).strip(),
                capabilities=list(data.get("capabilities", [])),
                execution_policy=dict(data.get("execution_policy", {})),
                priority=int(data.get("priority", 100)),
            )
        except Exception as exc:
            raise ManifestValidationError(f"Error constructing PluginManifest from '{source_path}': {exc}") from exc
