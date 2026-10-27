"""
Sprint H1.5D1.6C Studio Runtime Migration Integration Test.

Verifies:
1. EngineStudioCoordinator instantiates persistent InspectorRegistry with 6 Inspector Panels once at startup.
2. StudioLayoutManager switches active tab on keyboard shortcuts (keys 1-6, Tab, 'b').
3. StudioLauncher delegates active panel rendering to StudioLayoutManager and OpenCVRenderer.
"""

from __future__ import annotations

import logging
import unittest
import numpy as np

from camera_analytics.studio.coordinator import EngineStudioCoordinator
from camera_analytics.studio.launcher import StudioLauncher
from camera_analytics.studio.layout_manager import StudioLayoutManager
from camera_analytics.studio.renderers.opencv_renderer import OpenCVRenderer
from camera_analytics.viewer.window_manager import WindowManager


class TestStudioRuntimeMigration(unittest.TestCase):

    def test_01_coordinator_persistent_inspector_registry(self) -> None:
        """Verify EngineStudioCoordinator instantiates 6 inspectors once in InspectorRegistry."""
        coord = EngineStudioCoordinator()
        self.assertIsNotNone(coord.inspector_registry)
        self.assertEqual(len(coord.inspectors), 6)
        registered_keys = list(coord.inspector_registry._plugins.keys())
        self.assertIn("runtime_overview", registered_keys)
        self.assertIn("model_inspector", registered_keys)
        self.assertIn("human_runtime", registered_keys)
        self.assertIn("camera_inspector", registered_keys)
        self.assertIn("module", registered_keys)
        self.assertIn("event_timeline", registered_keys)

    def test_02_layout_manager_keyboard_navigation(self) -> None:
        """Verify StudioLayoutManager switches active tab index on hotkeys."""
        coord = EngineStudioCoordinator()
        lm = StudioLayoutManager()
        lm.set_inspectors(coord.inspectors)

        self.assertEqual(lm.active_index, 0)
        self.assertEqual(lm.active_tab_title, "Runtime Overview")

        # Press key '2' for AI Model
        lm.handle_key(ord("2"))
        self.assertEqual(lm.active_index, 1)
        self.assertIn("AI Model", lm.active_tab_title)

        # Press key '3' for Human Runtime
        lm.handle_key(ord("3"))
        self.assertEqual(lm.active_index, 2)
        self.assertIn("Human Runtime", lm.active_tab_title)

        # Press Tab for next tab (Camera)
        lm.handle_key(9)
        self.assertEqual(lm.active_index, 3)

        # Press 'b' for previous tab (Human Runtime)
        lm.handle_key(ord("b"))
        self.assertEqual(lm.active_index, 2)

    def test_03_studio_launcher_render_delegation(self) -> None:
        """Verify StudioLauncher uses StudioLayoutManager for rendering."""
        launcher = StudioLauncher(config={"enabled": True})
        launcher.initialize()
        self.assertTrue(launcher._is_initialized)

        # Handle key '2'
        switched = launcher.handle_key(ord("2"))
        self.assertTrue(switched)
        self.assertEqual(launcher.layout_manager.active_index, 1)

        wm = WindowManager()
        launcher.update_and_render(window_manager=wm)
        # Window title should be registered
        self.assertIn(launcher.window_title, wm._open_windows)
        wm.close_all()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    unittest.main()
