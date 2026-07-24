"""
Unit tests for Capability Negotiation Framework (Sprint 10E).

Verifies:
    1. Capability matching when all required capabilities are supported by Runtime.
    2. Capability mismatching when a module requires unsupported capability (e.g. 'REID', 'DEPTH'), updating state to UNSUPPORTED.
    3. Multiple capabilities matching.
    4. Empty capabilities matching (universally supported modules).
    5. CapabilityValidationReport summary generation.
"""

import unittest
from typing import Any, Optional

from camera_analytics.capability import (
    Capability,
    CapabilityNegotiator,
    CapabilitySet,
    RuntimeCapabilityProvider,
)
from camera_analytics.registry import ModuleDescriptor, ModuleManager, ModuleRegistry, ModuleState
from camera_analytics.runtime import AnalyticsRuntime
from camera_analytics.scene import SceneFactory
from camera_analytics.sdk import AnalyticsModule, AnalyticsResult


class CapabilityDummyModule(AnalyticsModule):
    """Test AnalyticsModule for capability negotiation validation."""

    def __init__(self, name: str) -> None:
        super().__init__(name=name)

    def update(self, context: Any) -> Optional[AnalyticsResult]:
        return AnalyticsResult(module_name=self.name)

    def process(self, scene: Any) -> AnalyticsResult:
        return AnalyticsResult(module_name=self.name)


class TestCapabilityNegotiation(unittest.TestCase):
    """Test suite for Capability Negotiation Framework."""

    def setUp(self) -> None:
        """Set up test environment."""
        self.provider = RuntimeCapabilityProvider(
            static_capabilities=[
                Capability.TRACKING,
                Capability.POSE,
                Capability.GROUND_POINT,
                Capability.ZONE,
                Capability.KEYPOINTS,
            ]
        )
        self.negotiator = CapabilityNegotiator(provider=self.provider)
        self.registry = ModuleRegistry()
        self.manager = ModuleManager(registry=self.registry)
        self.runtime = AnalyticsRuntime(module_manager=self.manager, capability_negotiator=self.negotiator)

    def tearDown(self) -> None:
        """Clean up runtime."""
        if self.runtime.is_running:
            self.runtime.stop()
        self.runtime.dispose()

    def test_capability_set_operations(self) -> None:
        """Test CapabilitySet operations: contains, is_subset_of, and missing_from."""
        runtime_caps = CapabilitySet.create(["TRACKING", "POSE", "ZONE"])
        mod_reqs = CapabilitySet.create(["TRACKING", "POSE"])

        self.assertTrue(mod_reqs.is_subset_of(runtime_caps))
        self.assertEqual(len(mod_reqs.missing_from(runtime_caps).capabilities), 0)

        unsupported_reqs = CapabilitySet.create(["TRACKING", "REID", "DEPTH"])
        self.assertFalse(unsupported_reqs.is_subset_of(runtime_caps))

        missing = unsupported_reqs.missing_from(runtime_caps)
        self.assertEqual(sorted(missing.to_list()), ["DEPTH", "REID"])

    def test_validation_1_capability_matching(self) -> None:
        """Test module with fully matching capabilities."""
        mod = CapabilityDummyModule(name="supported_mod")
        desc = ModuleDescriptor(
            module_id="supported_mod",
            module_name="Supported Module",
            capabilities=["TRACKING", "POSE"],
        )
        self.runtime.register_module(mod, desc)
        self.runtime.initialize()
        self.runtime.start()

        self.assertEqual(self.registry.get_descriptor("supported_mod").state, ModuleState.RUNNING)

    def test_validation_2_capability_mismatching(self) -> None:
        """Test module requiring unsupported capability (REID, DEPTH) transitions to UNSUPPORTED state and is skipped."""
        mod = CapabilityDummyModule(name="unsupported_reid_mod")
        desc = ModuleDescriptor(
            module_id="unsupported_reid_mod",
            module_name="REID Module",
            capabilities=["TRACKING", "REID", "DEPTH"],
        )
        self.runtime.register_module(mod, desc)
        self.runtime.initialize()
        self.runtime.start()

        # Descriptor state must be UNSUPPORTED, not RUNNING or FAILED
        self.assertEqual(self.registry.get_descriptor("unsupported_reid_mod").state, ModuleState.UNSUPPORTED)

        scene = SceneFactory.create_scene(frame_index=1, timestamp=0.03)
        res = self.runtime.process_scene(scene)

        # Unsupported module skipped cleanly without crashing kernel
        self.assertNotIn("unsupported_reid_mod", res.results)
        self.assertEqual(len(res.errors), 0)

    def test_validation_3_multiple_capabilities(self) -> None:
        """Test multiple modules with varying capability requirements."""
        mod_ok = CapabilityDummyModule(name="mod_ok")
        desc_ok = ModuleDescriptor(module_id="mod_ok", module_name="OK", capabilities=["POSE", "ZONE"])

        mod_fail = CapabilityDummyModule(name="mod_fail")
        desc_fail = ModuleDescriptor(module_id="mod_fail", module_name="Fail", capabilities=["SEGMENTATION"])

        self.runtime.register_module(mod_ok, desc_ok)
        self.runtime.register_module(mod_fail, desc_fail)

        report = self.runtime.get_capability_report()
        self.assertIn("mod_ok", report.supported_modules)
        self.assertIn("mod_fail", report.unsupported_modules)
        self.assertEqual(report.missing_capabilities["mod_fail"], ["SEGMENTATION"])

    def test_validation_4_empty_capabilities(self) -> None:
        """Test module with empty capabilities requirement is universally supported."""
        mod = CapabilityDummyModule(name="universal_mod")
        desc = ModuleDescriptor(module_id="universal_mod", module_name="Universal", capabilities=[])

        self.runtime.register_module(mod, desc)
        self.runtime.initialize()

        self.assertEqual(self.registry.get_descriptor("universal_mod").state, ModuleState.INITIALIZED)


if __name__ == "__main__":
    unittest.main()
