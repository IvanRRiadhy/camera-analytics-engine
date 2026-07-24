"""
Plugin Discovery & Manifest Framework Package.

Provides PluginManifest, ManifestLoader, ManifestValidationError, PluginDiscovery,
DiscoveryReport, and InvalidPluginRecord for discovering and validating plugin manifest JSON files
without dynamic module loading.
"""

from camera_analytics.discovery.loader import ManifestLoader, ManifestValidationError
from camera_analytics.discovery.manifest import PluginManifest
from camera_analytics.discovery.scanner import (
    DiscoveryReport,
    InvalidPluginRecord,
    PluginDiscovery,
)

__all__ = [
    "PluginManifest",
    "ManifestLoader",
    "ManifestValidationError",
    "PluginDiscovery",
    "DiscoveryReport",
    "InvalidPluginRecord",
]
