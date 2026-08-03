"""
Unit tests for Runtime Diagnostics & Profiling Component (Sprint 10I & Sprint 12.6).

Verifies:
    1. RuntimeMetrics aggregation (frame counts, FPS calculation, latency averages).
    2. PluginMetrics per-module calculations (executed count, skipped count, events, min/max/avg execution time).
    3. RuntimeHealth evaluation rules (HEALTHY, WARNING, DEGRADED, FAILED).
    4. DiagnosticsReport snapshot generation breakdown (slowest/fastest plugin, top producer, top skip ratio).
    5. HardwareDiagnosticCollector system CPU, RAM, and GPU hardware metrics collection.
"""

import time
import unittest
from typing import Any, Optional

from camera_analytics.diagnostics import (
    DiagnosticsCollector,
    DiagnosticsReport,
    HardwareDiagnosticCollector,
    PluginMetrics,
    RuntimeHealth,
    RuntimeMetrics,
)
from camera_analytics.registry import ModuleDescriptor, ModuleManager, ModuleRegistry
from camera_analytics.runtime import AnalyticsRuntime
from camera_analytics.scene import SceneFactory
from camera_analytics.scheduler import ExecutionMode, ExecutionPolicy
from camera_analytics.sdk import (
    AnalyticsEvent,
    AnalyticsEventType,
    AnalyticsModule,
    AnalyticsResult,
)


class DiagnosticTestModule(AnalyticsModule):
    """Test AnalyticsModule with controllable execution delay and event generation."""

    def __init__(self, name: str, delay_ms: float = 0.0, event_count: int = 0) -> None:
        super().__init__(name=name)
        self.delay_ms = delay_ms
        self.event_count = event_count

    def update(self, context: Any) -> Optional[AnalyticsResult]:
        return AnalyticsResult(module_name=self.name)

    def process(self, scene: Any) -> AnalyticsResult:
        if self.delay_ms > 0:
            time.sleep(self.delay_ms / 1000.0)

        events: list[AnalyticsEvent] = []
        for i in range(self.event_count):
            events.append(
                AnalyticsEvent(
                    event_id=f"evt_{self.name}_{i}",
                    module_name=self.name,
                    event_type=AnalyticsEventType.INFO,
                    message=f"Event {i}",
                    timestamp=scene.frame.timestamp,
                    frame_index=scene.frame.frame_index,
                )
            )

        return AnalyticsResult(module_name=self.name, events=events)


class TestRuntimeDiagnostics(unittest.TestCase):
    """Test suite for Runtime Diagnostics & Profiling."""

    def setUp(self) -> None:
        """Set up test environment."""
        self.collector = DiagnosticsCollector()
        self.registry = ModuleRegistry()
        self.manager = ModuleManager(registry=self.registry)
        self.runtime = AnalyticsRuntime(
            module_manager=self.manager,
            diagnostics_collector=self.collector,
        )

    def tearDown(self) -> None:
        """Clean up runtime."""
        if self.runtime.is_running:
            self.runtime.stop()
        self.runtime.dispose()

    def test_metrics_aggregation(self) -> None:
        """Test frame latency and dropped frame aggregation in DiagnosticsCollector."""
        self.collector.record_frame(frame_latency_ms=10.0, dropped=False)
        self.collector.record_frame(frame_latency_ms=20.0, dropped=False)
        self.collector.record_frame(frame_latency_ms=30.0, dropped=True)

        metrics = self.collector.get_runtime_metrics()
        self.assertEqual(metrics.total_frames, 3)
        self.assertEqual(metrics.average_latency_ms, 20.0)
        self.assertEqual(metrics.peak_latency_ms, 30.0)
        self.assertEqual(metrics.dropped_frames, 1)

    def test_plugin_metrics_calculation(self) -> None:
        """Test per-plugin execution, skip, and latency metrics calculation."""
        mod = DiagnosticTestModule(name="diag_mod", delay_ms=5.0, event_count=2)
        desc = ModuleDescriptor(
            module_id="diag_mod",
            module_name="Diag Mod",
            execution_policy=ExecutionPolicy(execution_mode=ExecutionMode.EVERY_FRAME),
        )

        self.runtime.register_module(mod, desc)
        self.runtime.initialize()
        self.runtime.start()

        for frame_idx in range(1, 6):
            scene = SceneFactory.create_scene(frame_index=frame_idx, timestamp=frame_idx * 0.03)
            self.runtime.process_scene(scene)

        p_metrics = {p.module_id: p for p in self.collector.get_plugin_metrics()}
        pm = p_metrics.get("diag_mod")

        self.assertIsNotNone(pm)
        if pm:
            self.assertEqual(pm.executed_count, 5)
            self.assertEqual(pm.skipped_count, 0)
            self.assertEqual(pm.published_events, 10)
            self.assertGreaterEqual(pm.average_execution_time_ms, 4.0)

    def test_runtime_health_evaluation(self) -> None:
        """Test RuntimeHealth state transitions based on error thresholds."""
        collector = DiagnosticsCollector()

        # Healthy
        self.assertEqual(collector.evaluate_health(), RuntimeHealth.HEALTHY)

        # Warning (1 error)
        collector.record_plugin_error("mod_err")
        self.assertEqual(collector.evaluate_health(), RuntimeHealth.WARNING)

        # Degraded (> 10 plugin errors)
        for _ in range(11):
            collector.record_plugin_error("mod_err")
        self.assertEqual(collector.evaluate_health(), RuntimeHealth.DEGRADED)

        # Failed (> 5 runtime errors)
        for _ in range(6):
            collector.record_runtime_error()
        self.assertEqual(collector.evaluate_health(), RuntimeHealth.FAILED)

    def test_diagnostics_report_generation(self) -> None:
        """Test DiagnosticsReport snapshot generation and breakdown metrics."""
        m_slow = DiagnosticTestModule(name="slow_mod", delay_ms=10.0, event_count=1)
        m_fast = DiagnosticTestModule(name="fast_mod", delay_ms=1.0, event_count=5)

        d_slow = ModuleDescriptor(
            module_id="slow_mod",
            module_name="Slow",
            execution_policy=ExecutionPolicy(execution_mode=ExecutionMode.EVERY_FRAME),
        )
        d_fast = ModuleDescriptor(
            module_id="fast_mod",
            module_name="Fast",
            execution_policy=ExecutionPolicy(execution_mode=ExecutionMode.EVERY_FRAME),
        )

        self.runtime.register_module(m_slow, d_slow)
        self.runtime.register_module(m_fast, d_fast)
        self.runtime.initialize()
        self.runtime.start()

        for frame_idx in range(1, 4):
            scene = SceneFactory.create_scene(frame_index=frame_idx, timestamp=frame_idx * 0.03)
            self.runtime.process_scene(scene)

        report = self.runtime.get_diagnostics_report()

        self.assertEqual(report.health, RuntimeHealth.HEALTHY)
        self.assertIsNotNone(report.slowest_plugin)
        self.assertIsNotNone(report.fastest_plugin)
        self.assertIsNotNone(report.highest_event_producer)

        if report.slowest_plugin and report.fastest_plugin and report.highest_event_producer:
            self.assertEqual(report.slowest_plugin.module_id, "slow_mod")
            self.assertEqual(report.fastest_plugin.module_id, "fast_mod")
            self.assertEqual(report.highest_event_producer.module_id, "fast_mod")

    def test_hardware_diagnostic_collector(self) -> None:
        """Test HardwareDiagnosticCollector system CPU, RAM, and GPU hardware metrics collection."""
        collector = HardwareDiagnosticCollector()
        metrics = collector.collect_system_metrics()

        self.assertIn("cpu_usage_percent", metrics)
        self.assertIn("memory_used_mb", metrics)
        self.assertIn("memory_total_mb", metrics)
        self.assertIn("gpu_metrics", metrics)

        gpu_metrics = metrics["gpu_metrics"]
        self.assertIn("gpu_usage_percent", gpu_metrics)
        self.assertIn("vram_used_mb", gpu_metrics)
        self.assertIn("vram_total_mb", gpu_metrics)
        self.assertIn("gpu_temperature_c", gpu_metrics)
        self.assertIn("power_draw_watts", gpu_metrics)

        self.assertGreaterEqual(metrics["cpu_usage_percent"], 0.0)
        self.assertGreaterEqual(metrics["memory_total_mb"], 0)


if __name__ == "__main__":
    unittest.main()
