"""
Unit tests for Module Registry & Module Management Layer (Sprint 10D).

Verifies:
    1. ModuleDescriptor instantiation and default values.
    2. ModuleRegistry register, unregister, enable, disable, and priority-sorted querying.
    3. ModuleManager orchestrating active RUNNING modules and metadata summary.
    4. Integration of AnalyticsRuntime Kernel with ModuleRegistry & ModuleManager.
"""

import unittest
from typing import Any, Optional

from camera_analytics.registry import ModuleDescriptor, ModuleManager, ModuleRegistry, ModuleState
from camera_analytics.runtime import AnalyticsRuntime, RuntimeContext
from camera_analytics.scene import SceneFactory
from camera_analytics.sdk import AnalyticsModule, AnalyticsResult


class PriorityTestModule(AnalyticsModule):
    """Test AnalyticsModule subclass with custom priority."""

    execution_order: list[str] = []

    def __init__(self, name: str, priority: int = 100) -> None:
        super().__init__(name=name)
        self.priority = priority

    def update(self, context: Any) -> Optional[AnalyticsResult]:
        return AnalyticsResult(module_name=self.name)

    def process(self, scene: Any) -> AnalyticsResult:
        PriorityTestModule.execution_order.append(self.name)
        return AnalyticsResult(module_name=self.name)


class TestModuleRegistry(unittest.TestCase):
    """Test suite for Module Registry & Module Management Layer."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        PriorityTestModule.execution_order.clear()
        self.registry = ModuleRegistry()
        self.manager = ModuleManager(registry=self.registry)
        self.runtime = AnalyticsRuntime(module_manager=self.manager)

    def tearDown(self) -> None:
        """Clean up runtime."""
        if self.runtime.is_running:
            self.runtime.stop()
        self.runtime.dispose()

    def test_module_descriptor_properties(self) -> None:
        """Test ModuleDescriptor fields and dictionary conversion."""
        desc = ModuleDescriptor(
            module_id="mod_test_1",
            module_name="Test Module 1",
            version="1.2.0",
            author="Dev Team",
            description="Unit Test Module",
            capabilities=["PEOPLE_COUNT"],
            priority=50,
            enabled=True,
            state=ModuleState.REGISTERED,
        )
        self.assertEqual(desc.module_id, "mod_test_1")
        self.assertEqual(desc.priority, 50)
        self.assertTrue(desc.enabled)
        self.assertEqual(desc.state, ModuleState.REGISTERED)

        desc_dict = desc.to_dict()
        self.assertEqual(desc_dict["state"], "REGISTERED")
        self.assertEqual(desc_dict["priority"], 50)

    def test_module_registry_operations(self) -> None:
        """Test ModuleRegistry register, unregister, enable, disable, and get_enabled priority sorting."""
        mod_high = PriorityTestModule(name="mod_high", priority=10)
        mod_low = PriorityTestModule(name="mod_low", priority=200)
        mod_mid = PriorityTestModule(name="mod_mid", priority=50)

        self.registry.register(mod_low)
        self.registry.register(mod_high)
        self.registry.register(mod_mid)

        # Priority ascending order check: high (10) -> mid (50) -> low (200)
        enabled_pairs = self.registry.get_enabled()
        self.assertEqual([d.module_id for d, _ in enabled_pairs], ["mod_high", "mod_mid", "mod_low"])

        # Disable mod_high
        self.registry.disable("mod_high")
        enabled_after_disable = self.registry.get_enabled()
        self.assertEqual([d.module_id for d, _ in enabled_after_disable], ["mod_mid", "mod_low"])

        # Enable mod_high back
        self.registry.enable("mod_high")
        enabled_after_enable = self.registry.get_enabled()
        self.assertEqual([d.module_id for d, _ in enabled_after_enable], ["mod_high", "mod_mid", "mod_low"])

        # Unregister mod_mid
        self.registry.unregister("mod_mid")
        self.assertIsNone(self.registry.get("mod_mid"))

    def test_module_manager_summary(self) -> None:
        """Test ModuleManager active module tracking and metadata summary generation."""
        mod1 = PriorityTestModule(name="mod1")
        mod2 = PriorityTestModule(name="mod2")

        self.manager.register_module(mod1)
        self.manager.register_module(mod2)

        summary = self.manager.to_summary()
        self.assertEqual(summary["total_registered"], 2)
        self.assertEqual(summary["total_enabled"], 2)

    def test_kernel_integration_with_module_registry(self) -> None:
        """Test AnalyticsRuntime Kernel using ModuleRegistry and enable/disable dynamic controls."""
        mod1 = PriorityTestModule(name="kernel_mod1", priority=1)
        mod2 = PriorityTestModule(name="kernel_mod2", priority=2)

        self.runtime.register_module(mod1)
        self.runtime.register_module(mod2)

        self.runtime.initialize()
        self.runtime.start()

        self.assertEqual(self.runtime.lifecycle_manager.get_state("kernel_mod1"), ModuleState.RUNNING)
        self.assertEqual(self.runtime.lifecycle_manager.get_state("kernel_mod2"), ModuleState.RUNNING)

        scene = SceneFactory.create_scene(frame_index=1, timestamp=0.03)
        self.runtime.process_scene(scene)

        # Both modules executed in priority order
        self.assertEqual(PriorityTestModule.execution_order, ["kernel_mod1", "kernel_mod2"])

        # Dynamically disable kernel_mod1 while kernel is running
        self.runtime.disable_module("kernel_mod1")
        PriorityTestModule.execution_order.clear()

        scene2 = SceneFactory.create_scene(frame_index=2, timestamp=0.06)
        self.runtime.process_scene(scene2)

        # Only kernel_mod2 executed because kernel_mod1 was disabled
        self.assertEqual(PriorityTestModule.execution_order, ["kernel_mod2"])


if __name__ == "__main__":
    unittest.main()
