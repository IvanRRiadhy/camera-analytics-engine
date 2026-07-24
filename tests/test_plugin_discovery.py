"""
Unit tests for Plugin Discovery & Manifest Framework (Sprint 10G).

Verifies:
    1. Valid manifest JSON parsing and PluginManifest object construction.
    2. Missing required field validation (plugin_id, version, sdk_version, entry_point).
    3. Invalid JSON syntax error handling.
    4. Directory scanning producing accurate DiscoveryReport statistics.
    5. Conversion of PluginManifest to ModuleDescriptor via to_descriptor().
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from camera_analytics.discovery import (
    ManifestLoader,
    ManifestValidationError,
    PluginDiscovery,
    PluginManifest,
)
from camera_analytics.registry import ModuleState
from camera_analytics.scheduler import ExecutionMode


class TestPluginDiscovery(unittest.TestCase):
    """Test suite for Plugin Discovery & Manifest Framework."""

    def setUp(self) -> None:
        """Set up temporary directory for manifest files."""
        self.test_dir = tempfile.mkdtemp(prefix="test_discovery_")
        self.loader = ManifestLoader()
        self.discovery = PluginDiscovery(loader=self.loader)

    def tearDown(self) -> None:
        """Clean up temporary directory."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_load_valid_manifest(self) -> None:
        """Test loading a fully compliant manifest JSON file."""
        manifest_path = Path(self.test_dir) / "manifest.json"
        content = {
            "plugin_id": "test_plugin_v1",
            "name": "Test Analytics Plugin",
            "version": "1.2.0",
            "sdk_version": "1.0.0",
            "entry_point": "plugins.test.TestPlugin",
            "capabilities": ["POSE", "TRACKING"],
            "execution_policy": {"execution_mode": "INTERVAL", "interval": 5},
            "priority": 15,
        }
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(content, f)

        manifest = self.loader.load_from_file(manifest_path)
        self.assertEqual(manifest.plugin_id, "test_plugin_v1")
        self.assertEqual(manifest.name, "Test Analytics Plugin")
        self.assertEqual(manifest.version, "1.2.0")
        self.assertEqual(manifest.capabilities, ["POSE", "TRACKING"])

        # Test to_descriptor conversion
        desc = manifest.to_descriptor()
        self.assertEqual(desc.module_id, "test_plugin_v1")
        self.assertEqual(desc.state, ModuleState.REGISTERED)
        self.assertEqual(desc.execution_policy.execution_mode, ExecutionMode.INTERVAL)
        self.assertEqual(desc.execution_policy.interval, 5)

    def test_missing_required_fields(self) -> None:
        """Test manifest lacking required fields raises ManifestValidationError."""
        manifest_path = Path(self.test_dir) / "broken_manifest.json"
        content = {
            "plugin_id": "broken_mod",
            # missing version, sdk_version, entry_point
        }
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(content, f)

        with self.assertRaises(ManifestValidationError) as ctx:
            self.loader.load_from_file(manifest_path)

        self.assertIn("Missing required fields", str(ctx.exception))

    def test_invalid_json_syntax(self) -> None:
        """Test malformed JSON syntax raises ManifestValidationError."""
        manifest_path = Path(self.test_dir) / "malformed.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            f.write("{ invalid json syntax ... ")

        with self.assertRaises(ManifestValidationError) as ctx:
            self.loader.load_from_file(manifest_path)

        self.assertIn("Invalid JSON syntax", str(ctx.exception))

    def test_plugin_discovery_scanning(self) -> None:
        """Test PluginDiscovery recursive directory scan separating valid and invalid manifests."""
        root = Path(self.test_dir)

        # Create 2 valid plugins
        p1 = root / "plugin1"
        p1.mkdir()
        with open(p1 / "manifest.json", "w", encoding="utf-8") as f:
            json.dump({
                "plugin_id": "p1",
                "version": "1.0",
                "sdk_version": "1.0",
                "entry_point": "mod1.Plugin",
            }, f)

        p2 = root / "plugin2"
        p2.mkdir()
        with open(p2 / "manifest.json", "w", encoding="utf-8") as f:
            json.dump({
                "plugin_id": "p2",
                "version": "2.0",
                "sdk_version": "1.0",
                "entry_point": "mod2.Plugin",
            }, f)

        # Create 1 broken plugin
        p3 = root / "broken"
        p3.mkdir()
        with open(p3 / "manifest.json", "w", encoding="utf-8") as f:
            json.dump({"plugin_id": "broken"}, f)  # missing required fields

        report = self.discovery.discover(root)

        self.assertEqual(report.found_count, 3)
        self.assertEqual(len(report.valid_plugins), 2)
        self.assertEqual(len(report.invalid_plugins), 1)

        valid_ids = [p.plugin_id for p in report.valid_plugins]
        self.assertIn("p1", valid_ids)
        self.assertIn("p2", valid_ids)


if __name__ == "__main__":
    unittest.main()
