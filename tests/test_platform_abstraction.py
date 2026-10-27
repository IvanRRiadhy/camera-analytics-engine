"""
Platform Abstraction & Strategy Unit Test Suite.

Verifies:
1. PlatformFactory dynamic class registry and environment overrides.
2. RuntimePlatform lifecycle hooks (initialize, verify_environment, shutdown, cleanup).
3. RuntimeCapabilityRegistry metadata and boolean flags.
4. Pure DI constructor injection in VideoSource and ModelManager.
5. Enterprise build profile loading and feature flags parsing.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from camera_analytics.core.human.backends.pytorch_backend import PyTorchBackend
from camera_analytics.core.human.inference_backend_base import IInferenceBackend
from camera_analytics.core.human.model_manager import ModelManager
from camera_analytics.core.video_backend import GStreamerBackend, IVideoBackend, OpenCVBackend
from camera_analytics.packaging.build_profile import load_profile
from camera_analytics.platform import (
    DockerPlatform,
    JetsonPlatform,
    LinuxPlatform,
    PlatformFactory,
    RuntimePlatform,
    WindowsPlatform,
)
from camera_analytics.platform.backend_factories import InferenceBackendFactory, VideoBackendFactory
from camera_analytics.sources.video_source import VideoSource


class TestPlatformAbstraction(unittest.TestCase):
    """Test suite for cross-platform abstraction layer."""

    def test_platform_factory_detection(self) -> None:
        """Test PlatformFactory detects environment and instantiates RuntimePlatform."""
        platform_obj = PlatformFactory.create_platform()
        self.assertIsInstance(platform_obj, RuntimePlatform)
        self.assertIn(platform_obj.name, ["windows", "linux", "jetson", "docker"])

    def test_platform_lifecycle_and_metadata(self) -> None:
        """Test RuntimePlatform lifecycle methods and capability metadata."""
        win = PlatformFactory.create_platform("WIN_X64")
        win.initialize()
        self.assertTrue(win.verify_environment())
        self.assertTrue(win.capabilities.has_capability("opencv"))
        self.assertIsNotNone(win.capabilities.get_metadata("os_platform"))
        win.shutdown()
        win.cleanup()

    def test_video_backend_factory_and_source_di(self) -> None:
        """Test VideoBackendFactory and pure DI constructor injection into VideoSource."""
        v_factory = VideoBackendFactory()
        cv_backend = v_factory.create_backend("test.mp4")
        self.assertIsInstance(cv_backend, OpenCVBackend)

        source = VideoSource(file_path="test.mp4", backend_factory=v_factory)
        self.assertIsNotNone(source.name)

    def test_inference_backend_factory_and_manager_di(self) -> None:
        """Test InferenceBackendFactory and pure DI constructor injection into ModelManager."""
        inf_factory = InferenceBackendFactory()
        manager = ModelManager(inference_factory=inf_factory)
        self.assertIsNotNone(manager)

    def test_build_profiles_and_feature_flags(self) -> None:
        """Test loading enterprise build profiles and parsing feature flags."""
        win_profile = load_profile("windows-release")
        self.assertTrue(win_profile["feature_flags"]["studio_gui"])
        self.assertFalse(win_profile["feature_flags"]["headless_mode"])

        jetson_profile = load_profile("jetson-release")
        self.assertTrue(jetson_profile["feature_flags"]["gstreamer"])
        self.assertTrue(jetson_profile["feature_flags"]["tensorrt"])
        self.assertTrue(jetson_profile["feature_flags"]["headless_mode"])


if __name__ == "__main__":
    unittest.main()
