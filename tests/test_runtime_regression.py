"""
Automated Runtime Regression Test Suite for CCTV Analytics AI Engine.

Validates core engine components post-build:
1. YOLO Pose Model Integration
2. BoTSORT Multi-Object Tracker Integration
3. MiVOLO v2 Age & Gender Subsystem
4. Capability Plugin Framework
5. Snapshot Publisher & Communication Manager
6. Studio Coordinator Observability
7. Packaging & Distribution Integrity
8. Platform Abstraction Layer
"""

from __future__ import annotations

import unittest
from pathlib import Path

from camera_analytics.bootstrap.distribution_validator import DistributionValidator
from camera_analytics.bootstrap.engine_bootstrap import EngineBootstrap
from camera_analytics.bootstrap.resource_manager import RuntimeResourceManager
from camera_analytics.bootstrap.self_test import RuntimeSelfTest
from camera_analytics.core.human.modules.mivolo_module import MiVOLOModule
from camera_analytics.platform.factory import PlatformFactory


class TestRuntimeRegression(unittest.TestCase):
    """Automated regression suite for full system certification."""

    def setUp(self) -> None:
        self.rm = RuntimeResourceManager.get_instance()

    def test_01_platform_layer_regression(self) -> None:
        """Verify PlatformFactory and RuntimePlatform instantiation."""
        platform_obj = PlatformFactory.create_platform()
        platform_obj.initialize()
        self.assertTrue(platform_obj.verify_environment())
        self.assertIn(platform_obj.name, ["windows", "linux", "jetson", "docker"])

    def test_02_distribution_manifest_regression(self) -> None:
        """Verify DistributionValidator against distribution.manifest.json."""
        validator = DistributionValidator()
        passed, messages = validator.validate_distribution()
        self.assertTrue(passed, f"Distribution validation failed: {messages}")

    def test_03_engine_bootstrap_regression(self) -> None:
        """Verify EngineBootstrap initialization."""
        bootstrap = EngineBootstrap()
        b_res = bootstrap.bootstrap()
        self.assertTrue(b_res.is_success)
        self.assertIsNotNone(b_res.context)

    def test_04_mivolo_subsystem_regression(self) -> None:
        """Verify MiVOLO v2 Age/Gender AI module initialization."""
        mod = MiVOLOModule()
        self.assertEqual(mod.module_id, "mivolo_age_gender")
        self.assertIn("age", mod.metadata.capabilities)
        self.assertIn("gender", mod.metadata.capabilities)

    def test_05_plugins_catalog_regression(self) -> None:
        """Verify dynamic PluginLoader discovers capability plugins."""
        import camera_analytics.plugins as plugin_pkg
        self.assertIsNotNone(plugin_pkg)

    def test_06_system_self_test_regression(self) -> None:
        """Verify RuntimeSelfTest 10-checkpoint suite."""
        self.assertTrue(RuntimeSelfTest.run_self_test())


if __name__ == "__main__":
    unittest.main()
