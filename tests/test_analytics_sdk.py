"""
Unit tests for Analytics SDK & Analytics Engine.

Verifies:
    - AnalyticsRegistry registration, lookup, dynamic instantiation, and listing.
    - AnalyticsModule lifecycle contract (initialize -> start -> update -> stop -> dispose).
    - AnalyticsManager lifecycle management and multi-module event dispatching.
    - Exception Isolation (isolated error recovery without crashing framework).
    - AnalyticsResult & AggregatedAnalyticsResult collection.
"""

import unittest
from typing import Optional

from camera_analytics.models import BoundingBox, Detection, Point, Track, Zone, ZoneType
from camera_analytics.sdk.dummy import DummyAnalytics
from camera_analytics.sdk.manager import AnalyticsManager
from camera_analytics.sdk.models import (
    AggregatedAnalyticsResult,
    AnalyticsContext,
    AnalyticsEvent,
    AnalyticsEventType,
    AnalyticsResult,
)
from camera_analytics.sdk.module import AnalyticsModule
from camera_analytics.sdk.registry import AnalyticsRegistry, register_analytics


class FaultyAnalytics(AnalyticsModule):
    """Faulty analytics plugin designed to test Exception Isolation."""

    def __init__(self, name: str = "faulty_analytics") -> None:
        super().__init__(name=name)
        self.should_fail_in_update = True

    def update(self, context: AnalyticsContext) -> AnalyticsResult:
        if self.should_fail_in_update:
            raise RuntimeError("Simulated crash inside FaultyAnalytics.update()")
        return AnalyticsResult(module_name=self.name)


class TestAnalyticsSDK(unittest.TestCase):
    """Test suite for Analytics SDK components."""

    def setUp(self) -> None:
        """Clear registry before each test."""
        AnalyticsRegistry.clear()

    def tearDown(self) -> None:
        """Clean up registry after test."""
        AnalyticsRegistry.clear()

    def test_analytics_registry_registration(self) -> None:
        """Test decorator registration and dynamic instantiation via AnalyticsRegistry."""
        @register_analytics("custom_test_analytics")
        class CustomTestAnalytics(AnalyticsModule):
            def __init__(self, name: str = "custom_test_analytics") -> None:
                super().__init__(name=name)

            def update(self, context: AnalyticsContext) -> AnalyticsResult:
                return AnalyticsResult(module_name=self.name)

        self.assertTrue(AnalyticsRegistry.is_registered("custom_test_analytics"))
        self.assertIn("custom_test_analytics", AnalyticsRegistry.list_registered())

        instance = AnalyticsRegistry.create("custom_test_analytics")
        self.assertIsInstance(instance, CustomTestAnalytics)
        self.assertEqual(instance.name, "custom_test_analytics")

    def test_analytics_module_lifecycle(self) -> None:
        """Test initialize, start, update, stop, and dispose lifecycle contract."""
        module = DummyAnalytics("dummy_lifecycle")
        ctx = AnalyticsContext(frame_context=None, runtime_state=None, track_manager=None, frame_index=1)

        self.assertFalse(module.is_initialized)
        self.assertFalse(module.is_running)

        module.initialize(ctx)
        self.assertTrue(module.is_initialized)

        module.start()
        self.assertTrue(module.is_running)

        res = module.update(ctx)
        self.assertEqual(res.module_name, "dummy_lifecycle")
        self.assertIn("active_tracks", res.metrics)

        module.stop()
        self.assertFalse(module.is_running)

        module.dispose()
        self.assertFalse(module.is_initialized)

    def test_analytics_manager_multi_module_execution(self) -> None:
        """Test AnalyticsManager running multiple modules concurrently."""
        mod1 = DummyAnalytics("dummy_1")
        mod2 = DummyAnalytics("dummy_2")

        manager = AnalyticsManager()
        manager.register_module(mod1)
        manager.register_module(mod2)

        ctx = AnalyticsContext(frame_context=None, runtime_state=None, track_manager=None, frame_index=1)
        manager.initialize(ctx)
        manager.start()

        from camera_analytics.models import DetectionClass
        det = Detection(bbox=BoundingBox(10, 10, 50, 100), confidence=0.9, detection_class=DetectionClass.PERSON)
        trk1 = Track(track_id=1, detection=det, first_frame=1, last_frame=1)

        aggregated = manager.process(ctx, tracks_created=[trk1])

        self.assertEqual(len(aggregated.results), 2)
        self.assertIn("dummy_1", aggregated.results)
        self.assertIn("dummy_2", aggregated.results)
        self.assertEqual(aggregated.results["dummy_1"].metrics["created_tracks_total"], 1)
        self.assertEqual(aggregated.results["dummy_2"].metrics["created_tracks_total"], 1)
        self.assertEqual(len(aggregated.errors), 0)

        manager.stop()
        manager.dispose()

    def test_exception_isolation(self) -> None:
        """Test that a crash in one analytics module does not stop other modules or crash the manager."""
        good_mod = DummyAnalytics("good_analytics")
        bad_mod = FaultyAnalytics("bad_analytics")

        manager = AnalyticsManager()
        manager.register_module(good_mod)
        manager.register_module(bad_mod)

        ctx = AnalyticsContext(frame_context=None, runtime_state=None, track_manager=None, frame_index=1)
        manager.initialize(ctx)
        manager.start()

        aggregated = manager.process(ctx)

        self.assertIn("good_analytics", aggregated.results)
        self.assertGreater(len(aggregated.errors), 0)
        self.assertTrue(any("FaultyAnalytics.update()" in err for err in aggregated.errors))

        manager.stop()
        manager.dispose()

    def test_analytics_result_aggregation(self) -> None:
        """Test aggregation of events, metrics, and execution time statistics."""
        mod = DummyAnalytics("result_mod")
        manager = AnalyticsManager()
        manager.register_module(mod)

        ctx = AnalyticsContext(frame_context=None, runtime_state=None, track_manager=None, frame_index=5)
        manager.initialize(ctx)
        manager.start()

        aggregated = manager.process(ctx)

        self.assertEqual(aggregated.frame_index, 5)
        self.assertGreaterEqual(aggregated.total_execution_time_ms, 0.0)
        self.assertIn("active_tracks", aggregated.summary_metrics)

        manager.stop()
        manager.dispose()


if __name__ == "__main__":
    unittest.main()
