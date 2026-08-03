"""
CLI Analytics Validation & Quality Gate Tool.

Executes recorded dataset videos through production AnalyticsRuntime, compares generated events
against ground truth annotations, computes accuracy/precision/recall/resource metrics,
and enforces CI/CD quality gates against versioned baselines.

Usage::

    python -m camera_analytics.tools.validate_dataset --dataset camera_analytics/datasets/sample_lobby_v1 --export all
    python -m camera_analytics.tools.validate_dataset --dataset camera_analytics/datasets/sample_lobby_v1 --compare-baseline camera_analytics/validation/baselines/sample_lobby_v1_v1.0.0.json
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from camera_analytics.validation import (
    AnalyticsMetricsEngine,
    BaselineComparisonError,
    BaselineManager,
    EventComparator,
    RuntimeReplayEngine,
    ValidationDataset,
    ValidationDatasetManager,
    ValidationHistoryStore,
    ValidationReportGenerator,
    ValidationTolerance,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("validate_dataset")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Enterprise CCTV Analytics Validation Framework CLI Tool"
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default="camera_analytics/datasets/sample_lobby_v1",
        help="Path to specific dataset directory or root datasets directory",
    )
    parser.add_argument(
        "--tag",
        type=str,
        default="",
        help="Filter dataset by tag (e.g. 'indoor', 'lobby')",
    )
    parser.add_argument(
        "--thresholds",
        type=str,
        default="0.35",
        help="Comma-separated confidence thresholds for sweep (e.g. '0.25,0.35,0.45')",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=200,
        help="Maximum frames limit for video replay",
    )
    parser.add_argument(
        "--export",
        type=str,
        default="all",
        choices=["json", "csv", "markdown", "all"],
        help="Export report format ('json', 'csv', 'markdown', 'all')",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="camera_analytics/validation/reports",
        help="Output directory for exported validation reports",
    )
    parser.add_argument(
        "--compare-baseline",
        type=str,
        default="",
        help="Path or version of baseline JSON file to compare against for CI/CD regression check",
    )
    parser.add_argument(
        "--save-baseline",
        type=str,
        default="",
        help="Version string (e.g. 'v1.0.0') to save current run as new baseline benchmark",
    )
    parser.add_argument(
        "--device",
        type=str,
        default="cuda",
        help="Compute device ('cuda' or 'cpu')",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    target_path = Path(args.dataset)

    datasets = []
    if target_path.is_dir() and (target_path / "manifest.json").exists() or (target_path / "ground_truth.json").exists():
        datasets.append(ValidationDataset(target_path))
    else:
        mgr = ValidationDatasetManager(target_path)
        mgr.discover_datasets()
        if args.tag:
            datasets = mgr.filter_by_tag(args.tag)
        else:
            datasets = list(mgr._datasets.values())

    if not datasets:
        logger.error("No valid validation datasets found at '%s'", args.dataset)
        sys.exit(1)

    threshold_list = [float(t.strip()) for t in args.thresholds.split(",") if t.strip()]

    comparator = EventComparator(tolerance=ValidationTolerance(frame_tolerance=15, time_tolerance=1.5))
    baseline_mgr = BaselineManager()
    history_store = ValidationHistoryStore()

    for ds in datasets:
        logger.info("================================================================================")
        logger.info("VALIDATING DATASET: %s (%s)", ds.manifest.dataset_id, ds.manifest.name)
        logger.info("================================================================================")

        for thresh in threshold_list:
            logger.info("--- Evaluating Confidence Threshold: %.2f ---", thresh)
            replay_engine = RuntimeReplayEngine(ds)
            generated_events, resource_metrics = replay_engine.run_replay(
                confidence_threshold=thresh,
                max_frames=args.max_frames,
                device=args.device,
            )

            match_results = comparator.compare(ds.ground_truth, generated_events)
            metrics = AnalyticsMetricsEngine.compute_metrics(match_results, resource_metrics)

            ds_info = {
                "dataset_id": ds.manifest.dataset_id,
                "version": ds.manifest.version,
                "scenario": ds.manifest.scenario,
                "tags": ds.manifest.tags,
                "confidence_threshold": thresh,
            }

            report_gen = ValidationReportGenerator(metrics, dataset_info=ds_info)
            exported = report_gen.export(args.output_dir, base_filename=f"report_{ds.manifest.dataset_id}_thresh_{thresh:.2f}")

            print("\n" + report_gen.to_markdown() + "\n")

            history_store.record_run(ds.manifest.dataset_id, metrics)

            if args.save_baseline:
                b_path = baseline_mgr.save_baseline(ds.manifest.dataset_id, args.save_baseline, metrics)
                logger.info("Saved new baseline benchmark to '%s'", b_path)

            if args.compare_baseline:
                logger.info("Executing CI/CD Quality Gate Regression Check against baseline '%s'...", args.compare_baseline)
                b_data = baseline_mgr.load_baseline(args.compare_baseline, ds.manifest.dataset_id)
                try:
                    res = baseline_mgr.compare_baseline(metrics, b_data)
                    logger.info("✅ CI/CD QUALITY GATE PASSED: No regression detected (F1=%f)", res["f1_score"]["current"])
                except BaselineComparisonError as err:
                    logger.error("❌ CI/CD QUALITY GATE FAILED REGRESSION CHECK: %s", err)
                    sys.exit(2)

    logger.info("Validation Framework execution completed successfully.")


if __name__ == "__main__":
    main()
