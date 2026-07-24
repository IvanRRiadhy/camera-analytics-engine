"""
Plugin Discovery Scanner Component.

Provides PluginDiscovery class scanning directory trees for manifest JSON files,
validating manifests via ManifestLoader, and returning comprehensive DiscoveryReport statistics.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence, Union

from camera_analytics.discovery.loader import ManifestLoader, ManifestValidationError
from camera_analytics.discovery.manifest import PluginManifest

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class InvalidPluginRecord:
    """Record describing a failed plugin manifest discovery.

    Attributes:
        manifest_path: File system path of manifest JSON.
        reason: Explanatory error text detailing why discovery failed.
    """

    manifest_path: str
    reason: str


@dataclass(slots=True)
class DiscoveryReport:
    """Report summarizing plugin discovery scan results.

    Attributes:
        found_count: Total number of manifest.json files discovered.
        valid_plugins: List of successfully loaded PluginManifest instances.
        invalid_plugins: List of InvalidPluginRecord describing failed manifests.
    """

    found_count: int = 0
    valid_plugins: list[PluginManifest] = field(default_factory=list)
    invalid_plugins: list[InvalidPluginRecord] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert discovery report to dictionary summary."""
        return {
            "found_count": self.found_count,
            "valid_count": len(self.valid_plugins),
            "invalid_count": len(self.invalid_plugins),
            "valid_plugins": [p.to_dict() for p in self.valid_plugins],
            "invalid_plugins": [
                {"path": r.manifest_path, "reason": r.reason} for r in self.invalid_plugins
            ],
        }


class PluginDiscovery:
    """Scanner inspecting directory trees to discover plugin manifests without dynamic module import."""

    def __init__(self, loader: Optional[ManifestLoader] = None) -> None:
        self._loader = loader or ManifestLoader()

    def discover(self, plugins_dir: Union[str, Path]) -> DiscoveryReport:
        """Scan directory tree recursively for all manifest.json files and validate contents.

        Args:
            plugins_dir: Root directory path to scan (e.g. 'plugins/').

        Returns:
            DiscoveryReport instance containing valid PluginManifests and invalid records.
        """
        root_path = Path(plugins_dir)
        report = DiscoveryReport()

        if not root_path.exists() or not root_path.is_dir():
            logger.warning("PluginDiscovery: Directory '%s' does not exist or is not a directory", plugins_dir)
            return report

        # Find all manifest.json files under root_path
        manifest_files = sorted(list(root_path.glob("**/manifest.json")))
        report.found_count = len(manifest_files)

        logger.info("PluginDiscovery: Discovered %d manifest.json file(s) under '%s'", report.found_count, root_path)

        for path in manifest_files:
            try:
                manifest = self._loader.load_from_file(path)
                report.valid_plugins.append(manifest)
                logger.info("PluginDiscovery: Successfully discovered valid plugin '%s' (v%s) from %s", manifest.plugin_id, manifest.version, path)
            except ManifestValidationError as exc:
                record = InvalidPluginRecord(manifest_path=str(path), reason=str(exc))
                report.invalid_plugins.append(record)
                logger.warning("PluginDiscovery: Invalid plugin manifest at '%s': %s", path, exc)
            except Exception as exc:
                record = InvalidPluginRecord(manifest_path=str(path), reason=f"Unexpected error loading manifest: {exc}")
                report.invalid_plugins.append(record)
                logger.error("PluginDiscovery: Unexpected error loading manifest at '%s': %s", path, exc)

        return report
