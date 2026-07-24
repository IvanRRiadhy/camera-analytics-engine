"""
Unit tests for Dynamic Plugin Loader Component (Sprint 10H).

Verifies:
    1. Successful dynamic import, reflection, type checking, and instantiation of a valid AnalyticsModule.
    2. ImportError status when Python module path does not exist.
    3. ClassNotFound status when target class is missing from Python module.
    4. InvalidType status when class does not inherit from AnalyticsModule.
    5. PluginLoadingReport breakdown generation (loaded vs rejected).
"""

import unittest
from typing import Any, Optional

from camera_analytics.discovery import PluginManifest
from camera_analytics.loader import PluginLoader
from camera_analytics.runtime import AnalyticsRuntime
from camera_analytics.sdk import AnalyticsModule, AnalyticsResult


# Valid AnalyticsModule for testing
class ValidTestModule(AnalyticsModule):
    """Valid test AnalyticsModule class inheriting from AnalyticsModule."""

    def __init__(self, name: str = "valid_test") -> None:
        super().__init__(name=name)

    def update(self, context: Any) -> Optional[AnalyticsResult]:
        return AnalyticsResult(module_name=self.name)

    def process(self, scene: Any) -> AnalyticsResult:
        return AnalyticsResult(module_name=self.name)


# Invalid class NOT inheriting from AnalyticsModule
class InvalidNonModuleClass:
    """Invalid class failing issubclass(cls, AnalyticsModule)."""

    def __init__(self) -> None:
        pass


class TestDynamicPluginLoader(unittest.TestCase):
    """Test suite for Dynamic Plugin Loader."""

    def setUp(self) -> None:
        """Set up test environment."""
        self.loader = PluginLoader()
        self.runtime = AnalyticsRuntime(plugin_loader=self.loader)

    def tearDown(self) -> None:
        """Clean up runtime."""
        if self.runtime.is_running:
            self.runtime.stop()
        self.runtime.dispose()

    def test_load_valid_plugin(self) -> None:
        """Test successful dynamic loading of a valid AnalyticsModule class."""
        manifest = PluginManifest(
            plugin_id="valid_mod",
            name="Valid Module",
            version="1.0.0",
            sdk_version="1.0.0",
            entry_point="camera_analytics.tests.test_dynamic_plugin_loader.ValidTestModule",
        )

        record = self.loader.load(manifest)
        self.assertEqual(record.status, "LOADED")
        self.assertIsNotNone(record.instance)
        self.assertIsInstance(record.instance, AnalyticsModule)
        self.assertEqual(record.instance.name, "valid_mod")

    def test_import_error_handling(self) -> None:
        """Test loading non-existent Python module path returns IMPORT_ERROR status."""
        manifest = PluginManifest(
            plugin_id="non_existent_mod",
            name="Non Existent",
            version="1.0.0",
            sdk_version="1.0.0",
            entry_point="camera_analytics.non_existent_package.FakeModule",
        )

        record = self.loader.load(manifest)
        self.assertEqual(record.status, "IMPORT_ERROR")
        self.assertIsNone(record.instance)
        self.assertIn("Failed to import", record.error_message or "")

    def test_class_not_found_handling(self) -> None:
        """Test loading non-existent class in existing module returns CLASS_NOT_FOUND status."""
        manifest = PluginManifest(
            plugin_id="missing_class_mod",
            name="Missing Class",
            version="1.0.0",
            sdk_version="1.0.0",
            entry_point="camera_analytics.tests.test_dynamic_plugin_loader.NonExistentClass",
        )

        record = self.loader.load(manifest)
        self.assertEqual(record.status, "CLASS_NOT_FOUND")
        self.assertIsNone(record.instance)
        self.assertIn("not found", record.error_message or "")

    def test_invalid_type_handling(self) -> None:
        """Test loading class that does not inherit from AnalyticsModule returns INVALID_TYPE status."""
        manifest = PluginManifest(
            plugin_id="invalid_type_mod",
            name="Invalid Type",
            version="1.0.0",
            sdk_version="1.0.0",
            entry_point="camera_analytics.tests.test_dynamic_plugin_loader.InvalidNonModuleClass",
        )

        record = self.loader.load(manifest)
        self.assertEqual(record.status, "INVALID_TYPE")
        self.assertIsNone(record.instance)
        self.assertIn("does not inherit from AnalyticsModule", record.error_message or "")

    def test_load_all_report_breakdown(self) -> None:
        """Test load_all aggregates statistics into PluginLoadingReport."""
        m_ok = PluginManifest(
            plugin_id="mod_ok",
            name="OK",
            version="1.0",
            sdk_version="1.0",
            entry_point="camera_analytics.tests.test_dynamic_plugin_loader.ValidTestModule",
        )
        m_imp = PluginManifest(
            plugin_id="mod_imp",
            name="Imp",
            version="1.0",
            sdk_version="1.0",
            entry_point="camera_analytics.fake.Fake",
        )
        m_cls = PluginManifest(
            plugin_id="mod_cls",
            name="Cls",
            version="1.0",
            sdk_version="1.0",
            entry_point="camera_analytics.tests.test_dynamic_plugin_loader.FakeClass",
        )
        m_typ = PluginManifest(
            plugin_id="mod_typ",
            name="Typ",
            version="1.0",
            sdk_version="1.0",
            entry_point="camera_analytics.tests.test_dynamic_plugin_loader.InvalidNonModuleClass",
        )

        report = self.loader.load_all([m_ok, m_imp, m_cls, m_typ])

        self.assertEqual(report.found_count, 4)
        self.assertEqual(report.loaded_count, 1)
        self.assertEqual(report.rejected_count, 3)
        self.assertEqual(report.import_error_count, 1)
        self.assertEqual(report.class_not_found_count, 1)
        self.assertEqual(report.invalid_type_count, 1)


if __name__ == "__main__":
    unittest.main()
