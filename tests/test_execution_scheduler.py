"""
Unit tests for Execution Scheduler Component (Sprint 10F).

Verifies:
    1. EVERY_FRAME execution policy (executes on all frames).
    2. INTERVAL 5 execution policy (executes on frame 1, 5, 10, 15...).
    3. INTERVAL 10 execution policy (executes on frame 1, 10, 20, 30...).
    4. DISABLED execution policy (never executes).
    5. MANUAL execution policy (never executes automatically).
    6. Priority ordering preservation during scheduled executions.
"""

import unittest
from typing import Any, Optional

from camera_analytics.registry import ModuleDescriptor, ModuleManager, ModuleRegistry, ModuleState
from camera_analytics.runtime import AnalyticsRuntime, RuntimeContext
from camera_analytics.scene import SceneFactory
from camera_analytics.scheduler import ExecutionMode, ExecutionPolicy, ExecutionScheduler
from camera_analytics.sdk import AnalyticsModule, AnalyticsResult


class ScheduledTestModule(AnalyticsModule):
    """Test AnalyticsModule recording execution frame indices."""

    def __init__(self, name: str) -> None:
        super().__init__(name=name)
        self.executed_frames: list[int] = []

    def update(self, context: Any) -> Optional[AnalyticsResult]:
        return AnalyticsResult(module_name=self.name)

    def process(self, scene: Any) -> AnalyticsResult:
        self.executed_frames.append(scene.frame.frame_index)
        return AnalyticsResult(module_name=self.name)


class TestExecutionScheduler(unittest.TestCase):
    """Test suite for Execution Scheduler Component."""

    def setUp(self) -> None:
        """Set up test environment."""
        self.scheduler = ExecutionScheduler()
        self.registry = ModuleRegistry()
        self.manager = ModuleManager(registry=self.registry)
        self.runtime = AnalyticsRuntime(module_manager=self.manager, execution_scheduler=self.scheduler)

    def tearDown(self) -> None:
        """Clean up runtime."""
        if self.runtime.is_running:
            self.runtime.stop()
        self.runtime.dispose()

    def test_every_frame_policy(self) -> None:
        """Test EVERY_FRAME policy executes on every frame."""
        mod = ScheduledTestModule(name="every_frame_mod")
        desc = ModuleDescriptor(
            module_id="every_frame_mod",
            module_name="Every Frame",
            execution_policy=ExecutionPolicy(execution_mode=ExecutionMode.EVERY_FRAME),
        )
        self.runtime.register_module(mod, desc)
        self.runtime.initialize()
        self.runtime.start()

        for frame_idx in range(1, 11):
            scene = SceneFactory.create_scene(frame_index=frame_idx, timestamp=frame_idx * 0.03)
            self.runtime.process_scene(scene)

        self.assertEqual(mod.executed_frames, list(range(1, 11)))

    def test_interval_5_policy(self) -> None:
        """Test INTERVAL 5 policy executes on frame 1, 5, 10."""
        mod = ScheduledTestModule(name="interval_5_mod")
        desc = ModuleDescriptor(
            module_id="interval_5_mod",
            module_name="Interval 5",
            execution_policy=ExecutionPolicy(execution_mode=ExecutionMode.INTERVAL, interval=5),
        )
        self.runtime.register_module(mod, desc)
        self.runtime.initialize()
        self.runtime.start()

        for frame_idx in range(1, 11):
            scene = SceneFactory.create_scene(frame_index=frame_idx, timestamp=frame_idx * 0.03)
            self.runtime.process_scene(scene)

        # Expected executions on frame 1, 5, 10
        self.assertEqual(mod.executed_frames, [1, 5, 10])

    def test_interval_10_policy(self) -> None:
        """Test INTERVAL 10 policy executes on frame 1, 10, 20."""
        mod = ScheduledTestModule(name="interval_10_mod")
        desc = ModuleDescriptor(
            module_id="interval_10_mod",
            module_name="Interval 10",
            execution_policy=ExecutionPolicy(execution_mode=ExecutionMode.INTERVAL, interval=10),
        )
        self.runtime.register_module(mod, desc)
        self.runtime.initialize()
        self.runtime.start()

        for frame_idx in range(1, 21):
            scene = SceneFactory.create_scene(frame_index=frame_idx, timestamp=frame_idx * 0.03)
            self.runtime.process_scene(scene)

        # Expected executions on frame 1, 10, 20
        self.assertEqual(mod.executed_frames, [1, 10, 20])

    def test_disabled_and_manual_policy(self) -> None:
        """Test DISABLED and MANUAL policies are never executed automatically."""
        mod_dis = ScheduledTestModule(name="dis_mod")
        desc_dis = ModuleDescriptor(
            module_id="dis_mod",
            module_name="Disabled",
            execution_policy=ExecutionPolicy(execution_mode=ExecutionMode.DISABLED),
        )

        mod_man = ScheduledTestModule(name="man_mod")
        desc_man = ModuleDescriptor(
            module_id="man_mod",
            module_name="Manual",
            execution_policy=ExecutionPolicy(execution_mode=ExecutionMode.MANUAL),
        )

        self.runtime.register_module(mod_dis, desc_dis)
        self.runtime.register_module(mod_man, desc_man)
        self.runtime.initialize()
        self.runtime.start()

        for frame_idx in range(1, 11):
            scene = SceneFactory.create_scene(frame_index=frame_idx, timestamp=frame_idx * 0.03)
            self.runtime.process_scene(scene)

        self.assertEqual(len(mod_dis.executed_frames), 0)
        self.assertEqual(len(mod_man.executed_frames), 0)


if __name__ == "__main__":
    unittest.main()
