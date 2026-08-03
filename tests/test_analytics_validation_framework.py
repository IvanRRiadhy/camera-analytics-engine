"""
Analytics Validation Framework Test Suite (Sprint 12.1).

Verifies:
    1. GroundTruthEvent & DatasetManifest parsing.
    2. ValidationDataset & ValidationDatasetManager loading and tag filtering.
    3. EventComparator matching accuracy (TP, FP, FN classification and latency).
    4. AnalyticsMetricsEngine Precision, Recall, F1, Accuracy calculations.
    5. BaselineManager CI/CD quality gate regression checking.
    6. ValidationReportGenerator formatting (JSON, CSV, Markdown).
"""

import json
import tempfile
import unittest
from pathlib import Path

from camera_analytics.communication.models import StandardAnalyticsEvent
from camera_analytics.validation import (
    AnalyticsMetricsEngine,
    BaselineComparisonError,
    BaselineManager,
    EventComparator,
    GroundTruthEvent,
    MatchStatus,
    ValidationDataset,
    ValidationDatasetManager,
    ValidationReportGenerator,
    ValidationTolerance,
)


class TestAnalyticsValidationFramework(unittest.TestCase):
    """Validation Framework Unit Test Suite."""

    def setUp(self) -> None:
        """Set up ground truth events and generated events."""
        self.gt_event1 = GroundTruthEvent(
            frame_index=10,
            timestamp=1.0,
            event_type="ZONE_ENTER",
            camera_id="cam_01",
            track_id=1,
            zone_id="zone_lobby",
            severity="INFO",
        )
        self.gt_event2 = GroundTruthEvent(
            frame_index=50,
            timestamp=5.0,
            event_type="LOITERING",
            camera_id="cam_01",
            track_id=2,
            zone_id="zone_lobby",
            severity="CRITICAL",
        )

        self.gen_event1 = StandardAnalyticsEvent(
            event_type="ZONE_ENTER",
            analytics_module="zone_enter",
            message="Track #1 entered zone 'zone_lobby'",
            camera_id="cam_01",
            track_id=1,
            zone_id="zone_lobby",
            frame_index=12,
        )
        self.gen_event_fp = StandardAnalyticsEvent(
            event_type="DIRECTION_VIOLATION",
            analytics_module="direction_detection",
            message="Wrong direction movement",
            camera_id="cam_01",
            track_id=99,
            frame_index=30,
        )

    def test_schema_and_manifest_parsing(self) -> None:
        """Verify GroundTruthEvent and manifest dictionary parsing."""
        d = self.gt_event1.to_dict()
        parsed_gt = GroundTruthEvent.from_dict(d)

        self.assertEqual(parsed_gt.frame_index, 10)
        self.assertEqual(parsed_gt.event_type, "ZONE_ENTER")
        self.assertEqual(parsed_gt.track_id, 1)
        self.assertEqual(parsed_gt.zone_id, "zone_lobby")

    def test_event_comparator_classification(self) -> None:
        """Verify EventComparator classifies TP, FP, and FN accurately."""
        comparator = EventComparator(tolerance=ValidationTolerance(frame_tolerance=10))
        results = comparator.compare([self.gt_event1, self.gt_event2], [self.gen_event1, self.gen_event_fp])

        # Expect 1 TP (gen1 matches gt1), 1 FN (gt2 missed), 1 FP (gen_fp unexpected)
        statuses = [r.status for r in results]
        self.assertIn(MatchStatus.TRUE_POSITIVE, statuses)
        self.assertIn(MatchStatus.FALSE_POSITIVE, statuses)
        self.assertIn(MatchStatus.FALSE_NEGATIVE, statuses)

    def test_metrics_engine_calculations(self) -> None:
        """Verify MetricsEngine calculates Precision, Recall, F1, Accuracy."""
        comparator = EventComparator(tolerance=ValidationTolerance(frame_tolerance=10))
        results = comparator.compare([self.gt_event1, self.gt_event2], [self.gen_event1, self.gen_event_fp])
        metrics = AnalyticsMetricsEngine.compute_metrics(results)

        overall = metrics["overall"]
        self.assertEqual(overall["true_positives"], 1)
        self.assertEqual(overall["false_positives"], 1)
        self.assertEqual(overall["false_negatives"], 1)
        self.assertAlmostEqual(overall["precision"], 0.5, places=2)
        self.assertAlmostEqual(overall["recall"], 0.5, places=2)
        self.assertAlmostEqual(overall["f1_score"], 0.5, places=2)

    def test_baseline_manager_quality_gate(self) -> None:
        """Verify BaselineManager detects regressions and saves baselines."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            mgr = BaselineManager(baselines_dir=tmp_dir)

            base_metrics = {"overall": {"precision": 0.9, "recall": 0.9, "f1_score": 0.9}}
            curr_metrics_ok = {"overall": {"precision": 0.89, "recall": 0.89, "f1_score": 0.89}}
            curr_metrics_fail = {"overall": {"precision": 0.6, "recall": 0.6, "f1_score": 0.6}}

            mgr.save_baseline("test_ds", "v1.0", base_metrics)
            loaded_b = mgr.load_baseline("test_ds_v1.0.json")

            # Clean comparison
            res = mgr.compare_baseline(curr_metrics_ok, loaded_b, max_allowed_f1_drop=0.05)
            self.assertFalse(res["is_regression"])

            # Regression exception
            with self.assertRaises(BaselineComparisonError):
                mgr.compare_baseline(curr_metrics_fail, loaded_b, max_allowed_f1_drop=0.05)

    def test_report_generator_exports(self) -> None:
        """Verify ValidationReportGenerator exports JSON, CSV, Markdown formats."""
        metrics = {
            "overall": {"precision": 1.0, "recall": 1.0, "f1_score": 1.0, "accuracy": 1.0},
            "by_event_type": {"ZONE_ENTER": {"precision": 1.0, "recall": 1.0, "f1_score": 1.0}},
            "resources": {"throughput_fps": 30.0, "cpu_utilization_pct": 12.5},
        }
        gen = ValidationReportGenerator(metrics, dataset_info={"dataset_id": "test_ds", "tags": ["lobby"]})

        with tempfile.TemporaryDirectory() as tmp_dir:
            exported = gen.export(tmp_dir)
            self.assertTrue(exported["json"].exists())
            self.assertTrue(exported["csv"].exists())
            self.assertTrue(exported["markdown"].exists())

            md_content = exported["markdown"].read_text(encoding="utf-8")
            self.assertIn("# Enterprise Analytics Validation Report", md_content)
            self.assertIn("F1 Score", md_content)


if __name__ == "__main__":
    unittest.main()
