"""
Unit tests for Analytics Runtime Kernel Skeleton.

Verifies:
    - RuntimeContext dependency container service registration.
    - LifecycleManager module state transitions (UNINITIALIZED -> INITIALIZED -> ACTIVE -> STOPPED -> DISPOSED).
    - ExecutionEngine dispatching immutable Scene snapshots with Exception Isolation.
    - AnalyticsRuntime kernel orchestration.
"""

import unittest
from typing import Any, Optional

from camera_analytics.entities.models import CameraEntity, FrameEntity
from camera_analytics.runtime import (
    AnalyticsRuntime,
    ExecutionEngine,
    LifecycleManager,
    ModuleState,
    RuntimeContext,
)
from camera_analytics.scene import SceneFactory
from camera_analytics.sdk import AnalyticsModule, AnalyticsResult


class MockModule(AnalyticsModule):
    """Concrete mock module for testing LifecycleManager and ExecutionEngine."""

    def __init__(self, name: str = "mock_module") -> None:
        super().__init__(name=name)

    def update(self, context: Any) -> Optional[AnalyticsResult]:
        return AnalyticsResult(module_name=self.name)

    def process(self, scene: Any) -> AnalyticsResult:
        return AnalyticsResult(module_name=self.name)


class FaultyModule(AnalyticsModule):
    """Faulty module for testing Exception Isolation Barrier."""

    def __init__(self, name: str = "faulty_module") -> None:
        super().__init__(name=name)

    def update(self, context: Any) -> Optional[AnalyticsResult]:
        raise RuntimeError("Simulated crash inside FaultyModule.update()")

    def process(self, scene: Any) -> AnalyticsResult:
        raise RuntimeError("Simulated crash inside FaultyModule.process()")


class TestAnalyticsRuntimeKernel(unittest.TestCase):
    """Test suite for Analytics Runtime Kernel Skeleton components."""

    def setUp(self) -> None:
        """Set up test context."""
        self.cam_ent = CameraEntity(camera_id="cam_kernel_test", camera_name="Test Camera")
        self.context = RuntimeContext(camera=self.cam_ent)

    def test_runtime_context_services(self) -> None:
        """Test RuntimeContext service registration and retrieval."""
        self.context.register_service("test_service", "service_instance")
        self.assertEqual(self.context.get_service("test_service"), "service_instance")
        self.assertIsNone(self.context.get_service("non_existent"))

    def test_lifecycle_manager_transitions(self) -> None:
        """Test LifecycleManager state machine transitions."""
        mgr = LifecycleManager(runtime_context=self.context)
        dummy = MockModule(name="dummy_test")

        mgr.register(dummy)
        self.assertEqual(mgr.get_state("dummy_test"), ModuleState.REGISTERED)

        mgr.initialize_module("dummy_test")
        self.assertEqual(mgr.get_state("dummy_test"), ModuleState.INITIALIZED)

        mgr.start_module("dummy_test")
        self.assertEqual(mgr.get_state("dummy_test"), ModuleState.RUNNING)

        mgr.pause_module("dummy_test")
        self.assertEqual(mgr.get_state("dummy_test"), ModuleState.STOPPED)

        mgr.stop_module("dummy_test")
        self.assertEqual(mgr.get_state("dummy_test"), ModuleState.STOPPED)

        mgr.dispose_module("dummy_test")
        self.assertEqual(mgr.get_state("dummy_test"), ModuleState.DISPOSED)

    def test_execution_engine_exception_isolation(self) -> None:
        """Test ExecutionEngine dispatching Scene to modules with Exception Isolation."""
        mgr = LifecycleManager(runtime_context=self.context)
        good_mod = MockModule(name="good_module")
        bad_mod = FaultyModule(name="bad_module")

        mgr.register(good_mod)
        mgr.register(bad_mod)

        mgr.start_all()

        exec_engine = ExecutionEngine(lifecycle_manager=mgr, runtime_context=self.context)
        scene = SceneFactory.create_scene(frame_index=1, timestamp=0.1)

        aggregated = exec_engine.execute_scene(scene)

        # Good module executes, bad module fails safely without crashing kernel
        self.assertEqual(len(aggregated.results), 1)
        self.assertEqual(len(aggregated.errors), 1)
        self.assertIn("bad_module", aggregated.errors[0])

    def test_analytics_runtime_kernel_orchestration(self) -> None:
        """Test AnalyticsRuntime kernel orchestration lifecycle and scene processing."""
        runtime = AnalyticsRuntime(context=self.context)
        mod = MockModule(name="module_test")

        runtime.register_module(mod)
        runtime.initialize()
        runtime.start()

        self.assertTrue(runtime.is_running)

        scene = SceneFactory.create_scene(frame_index=10, timestamp=1.0)
        result = runtime.process_scene(scene)

        self.assertIsNotNone(result)
        self.assertEqual(result.frame_index, 10)

        runtime.stop()
        self.assertFalse(runtime.is_running)

        runtime.dispose()


if __name__ == "__main__":
    unittest.main()
