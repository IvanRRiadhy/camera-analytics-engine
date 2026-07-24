"""
Unit tests for Analytics Runtime Kernel Hardening & Stress Validation (Sprint 10C).

Validates:
    1. Concurrent execution of 5+ Analytics Modules.
    2. Exception Isolation Barrier when one plugin throws unhandled RuntimeError.
    3. Plugin Lifecycle state transitions and hook execution order.
    4. Deterministic module execution order.
    5. Context and service injection into Analytics Modules.
    6. AggregatedAnalyticsResult aggregation and RuntimeStatistics tracking.
"""

import unittest
from typing import Any, Optional

from camera_analytics.entities.models import CameraEntity
from camera_analytics.runtime import (
    AnalyticsRuntime,
    ExecutionEngine,
    LifecycleManager,
    ModuleState,
    RuntimeContext,
)
from camera_analytics.scene import SceneFactory
from camera_analytics.sdk import AnalyticsEvent, AnalyticsEventType, AnalyticsModule, AnalyticsResult


class OrderedTrackerModule(AnalyticsModule):
    """Tracker module that records execution sequence."""

    execution_log: list[str] = []

    def __init__(self, name: str) -> None:
        super().__init__(name=name)
        self.received_context: Optional[Any] = None

    def on_initialize(self, context: Any) -> None:
        self.received_context = context

    def update(self, context: Any) -> Optional[AnalyticsResult]:
        return AnalyticsResult(module_name=self.name)

    def process(self, scene: Any) -> AnalyticsResult:
        OrderedTrackerModule.execution_log.append(self.name)
        evt = AnalyticsEvent(
            event_id=f"evt_{self.name}_{scene.frame.frame_index}",
            module_name=self.name,
            event_type=AnalyticsEventType.INFO,
            message=f"Event from {self.name}",
            timestamp=scene.frame.timestamp,
            frame_index=scene.frame.frame_index,
        )
        return AnalyticsResult(module_name=self.name, events=[evt])


class CrashingFaultyModule(AnalyticsModule):
    """Module designed to crash during process execution."""

    def __init__(self, name: str = "faulty_crash_module") -> None:
        super().__init__(name=name)

    def update(self, context: Any) -> Optional[AnalyticsResult]:
        raise RuntimeError(f"Deliberate crash in module '{self.name}'")

    def process(self, scene: Any) -> AnalyticsResult:
        raise RuntimeError(f"Deliberate crash in module '{self.name}'")


class TestRuntimeHardening(unittest.TestCase):
    """Stress and Hardening Test Suite for Analytics Runtime Kernel."""

    def setUp(self) -> None:
        """Set up test environment."""
        OrderedTrackerModule.execution_log.clear()
        self.cam = CameraEntity(camera_id="cam_hardening", camera_name="Hardening Cam")
        self.context = RuntimeContext(camera=self.cam)
        self.context.register_service("global_logger", "mock_logger_service")
        self.runtime = AnalyticsRuntime(context=self.context)

    def tearDown(self) -> None:
        """Clean up runtime."""
        if self.runtime.is_running:
            self.runtime.stop()
        self.runtime.dispose()

    def test_validation_1_and_2_multi_plugin_concurrency_and_exception_isolation(self) -> None:
        """Validate 5+ plugins running concurrently and 1 faulty plugin crashing safely."""
        plugins = [OrderedTrackerModule(name=f"dummy_{i}") for i in range(1, 6)]
        faulty = CrashingFaultyModule(name="faulty_plugin")

        for p in plugins:
            self.runtime.register_module(p)
        self.runtime.register_module(faulty)

        self.runtime.initialize()
        self.runtime.start()

        self.assertTrue(self.runtime.is_running)

        scene = SceneFactory.create_scene(frame_index=1, timestamp=0.03)
        aggregated = self.runtime.process_scene(scene)

        # 5 plugins executed successfully, 1 failed safely
        self.assertEqual(len(aggregated.results), 5)
        self.assertEqual(len(aggregated.errors), 1)
        self.assertIn("faulty_plugin", aggregated.errors[0])
        self.assertTrue(self.runtime.is_running)  # Kernel stays alive

    def test_validation_3_lifecycle_transitions(self) -> None:
        """Validate complete plugin lifecycle states: initialize -> start -> process -> stop -> dispose."""
        mgr = self.runtime.lifecycle_manager
        mod = OrderedTrackerModule(name="lifecycle_mod")

        self.runtime.register_module(mod)
        self.assertEqual(mgr.get_state("lifecycle_mod"), ModuleState.REGISTERED)

        self.runtime.initialize()
        self.assertEqual(mgr.get_state("lifecycle_mod"), ModuleState.INITIALIZED)

        self.runtime.start()
        self.assertEqual(mgr.get_state("lifecycle_mod"), ModuleState.RUNNING)

        scene = SceneFactory.create_scene(frame_index=2, timestamp=0.06)
        res = self.runtime.process_scene(scene)
        self.assertIn("lifecycle_mod", res.results)

        self.runtime.stop()
        self.assertEqual(mgr.get_state("lifecycle_mod"), ModuleState.STOPPED)

        mgr.dispose_module("lifecycle_mod")
        self.assertEqual(mgr.get_state("lifecycle_mod"), ModuleState.DISPOSED)

    def test_validation_4_deterministic_execution_order(self) -> None:
        """Validate that plugins execute in exact registered deterministic order."""
        names = ["mod_alpha", "mod_beta", "mod_gamma", "mod_delta", "mod_epsilon"]
        for n in names:
            self.runtime.register_module(OrderedTrackerModule(name=n))

        self.runtime.initialize()
        self.runtime.start()

        scene = SceneFactory.create_scene(frame_index=3, timestamp=0.09)
        self.runtime.process_scene(scene)

        self.assertEqual(OrderedTrackerModule.execution_log, names)

    def test_validation_5_context_injection(self) -> None:
        """Validate RuntimeContext and extra services injection into plugins."""
        mod = OrderedTrackerModule(name="context_mod")
        self.runtime.register_module(mod)
        self.runtime.initialize()

        self.assertIsNotNone(mod.received_context)
        self.assertEqual(self.context.get_service("global_logger"), "mock_logger_service")

    def test_validation_6_and_7_result_aggregation_and_runtime_statistics(self) -> None:
        """Validate AggregatedAnalyticsResult aggregation and RuntimeStatistics metric tracking."""
        for i in range(1, 4):
            self.runtime.register_module(OrderedTrackerModule(name=f"mod_{i}"))

        self.runtime.initialize()
        self.runtime.start()

        for frame_idx in range(1, 11):
            scene = SceneFactory.create_scene(frame_index=frame_idx, timestamp=frame_idx * 0.03)
            aggregated = self.runtime.process_scene(scene)
            self.assertEqual(len(aggregated.all_events), 3)

        stats = self.context.statistics
        self.assertEqual(stats.total_processed_scenes, 10)
        self.assertEqual(stats.total_events_emitted, 30)
        self.assertGreater(stats.total_execution_time_ms, 0.0)
        self.assertEqual(stats.plugin_execution_counts["mod_1"], 10)
        self.assertEqual(stats.plugin_execution_counts["mod_2"], 10)
        self.assertEqual(stats.plugin_execution_counts["mod_3"], 10)


if __name__ == "__main__":
    unittest.main()
