"""
Service Discovery Subsystem Implementation.

Scans plugin directories for `manifest.json` files and parses metadata specifications.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from camera_analytics.services.manifest import ServiceManifest

logger = logging.getLogger(__name__)


class ServiceDiscovery:
    """Discovers service plugins by scanning directories for manifest.json files."""

    def __init__(self, search_dir: str | Path = "camera_analytics/services/plugins") -> None:
        self.search_dir = Path(search_dir).resolve()

    def discover_manifests(self) -> dict[str, tuple[ServiceManifest, Path]]:
        """Scan directory and parse all manifest.json files.

        Returns:
            Dictionary mapping service_name -> (ServiceManifest, plugin_folder_path).
        """
        manifests: dict[str, tuple[ServiceManifest, Path]] = {}

        if not self.search_dir.exists():
            logger.warning("ServiceDiscovery: Directory '%s' does not exist", self.search_dir)
            return manifests

        for manifest_file in self.search_dir.glob("**/manifest.json"):
            try:
                manifest = ServiceManifest.from_file(manifest_file)
                plugin_dir = manifest_file.parent
                manifests[manifest.service_name] = (manifest, plugin_dir)
                logger.info("ServiceDiscovery: Discovered service '%s' v%s at '%s'", manifest.service_name, manifest.version, plugin_dir)
            except Exception as exc:
                logger.error("ServiceDiscovery: Failed to parse manifest '%s': %s", manifest_file, exc)

        return manifests
