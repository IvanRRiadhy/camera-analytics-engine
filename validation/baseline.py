"""
Baseline Manager & Validation History Persistence.

Saves, loads, and compares validation run metrics against versioned baselines for CI/CD regression testing.
Persists validation history in camera_analytics/validation/history/ for long-term trend analysis.
"""

from __future__ import annotations

import datetime
import json
import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class BaselineComparisonError(Exception):
    """Raised when validation metrics fall below an acceptable regression threshold."""

    pass


class BaselineManager:
    """Manages loading, saving, and comparing validation metrics against baseline benchmarks."""

    def __init__(self, baselines_dir: str | Path = "camera_analytics/validation/baselines") -> None:
        self.baselines_dir = Path(baselines_dir)
        self.baselines_dir.mkdir(parents=True, exist_ok=True)

    def save_baseline(self, dataset_id: str, version: str, metrics: dict[str, Any]) -> Path:
        """Save current metric evaluation as a versioned baseline JSON file.

        Args:
            dataset_id: Dataset identifier.
            version: Baseline version identifier (e.g. 'v1.0.0').
            metrics: Metrics evaluation dictionary.

        Returns:
            Path to written baseline file.
        """
        filename = f"{dataset_id}_{version}.json"
        target_path = self.baselines_dir / filename

        payload = {
            "dataset_id": dataset_id,
            "version": version,
            "saved_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "metrics": metrics,
        }

        target_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("BaselineManager saved baseline benchmark: %s", target_path)
        return target_path

    def load_baseline(self, baseline_path_or_version: str | Path, dataset_id: Optional[str] = None) -> dict[str, Any]:
        """Load baseline benchmark metrics file from disk."""
        path_obj = Path(baseline_path_or_version)
        if not path_obj.exists():
            candidate = self.baselines_dir / baseline_path_or_version
            if candidate.exists():
                path_obj = candidate
            elif dataset_id:
                candidate_id = self.baselines_dir / f"{dataset_id}_{baseline_path_or_version}.json"
                if candidate_id.exists():
                    path_obj = candidate_id

        if not path_obj.exists():
            raise FileNotFoundError(f"Baseline benchmark file '{path_obj}' not found.")

        data = json.loads(path_obj.read_text(encoding="utf-8"))
        logger.info("BaselineManager loaded baseline from '%s'", path_obj)
        return data

    def compare_baseline(
        self,
        current_metrics: dict[str, Any],
        baseline_metrics: dict[str, Any],
        max_allowed_f1_drop: float = 0.02,
    ) -> dict[str, Any]:
        """Compare current metrics against baseline benchmark metrics and check for regressions.

        Args:
            current_metrics: Current run metrics dictionary.
            baseline_metrics: Loaded baseline metrics dictionary.
            max_allowed_f1_drop: Maximum acceptable F1 drop (default 0.02 or 2%).

        Returns:
            Comparison evaluation result.

        Raises:
            BaselineComparisonError: If current F1 score dropped beyond max_allowed_f1_drop.
        """
        curr_overall = current_metrics.get("overall", {})
        base_overall = baseline_metrics.get("metrics", {}).get("overall", baseline_metrics.get("overall", {}))

        curr_f1 = curr_overall.get("f1_score", 0.0)
        base_f1 = base_overall.get("f1_score", 0.0)
        f1_delta = curr_f1 - base_f1

        curr_prec = curr_overall.get("precision", 0.0)
        base_prec = base_overall.get("precision", 0.0)

        curr_rec = curr_overall.get("recall", 0.0)
        base_rec = base_overall.get("recall", 0.0)

        is_regression = f1_delta < -max_allowed_f1_drop

        res = {
            "is_regression": is_regression,
            "f1_score": {"current": curr_f1, "baseline": base_f1, "delta": round(f1_delta, 4)},
            "precision": {"current": curr_prec, "baseline": base_prec, "delta": round(curr_prec - base_prec, 4)},
            "recall": {"current": curr_rec, "baseline": base_rec, "delta": round(curr_rec - base_rec, 4)},
            "max_allowed_f1_drop": max_allowed_f1_drop,
        }

        if is_regression:
            msg = f"CI/CD Quality Gate Regression Failed: F1 score dropped by {abs(f1_delta)*100:.2f}% (Current: {curr_f1:.4f}, Baseline: {base_f1:.4f}, Max Allowed Drop: {max_allowed_f1_drop*100:.1f}%)"
            logger.error(msg)
            raise BaselineComparisonError(msg)

        logger.info("Baseline comparison passed cleanly: F1 delta = %+.4f", f1_delta)
        return res


class ValidationHistoryStore:
    """Persists validation run history for long-term trend analysis."""

    def __init__(self, history_dir: str | Path = "camera_analytics/validation/history") -> None:
        self.history_dir = Path(history_dir)
        self.history_dir.mkdir(parents=True, exist_ok=True)

    def record_run(self, dataset_id: str, metrics: dict[str, Any]) -> Path:
        """Record validation run entry into history log.

        Args:
            dataset_id: Dataset identifier.
            metrics: Metrics evaluation dictionary.

        Returns:
            Path to recorded history file.
        """
        now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
        file_path = self.history_dir / f"run_{dataset_id}_{now_str}.json"

        record = {
            "dataset_id": dataset_id,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "metrics": metrics,
        }

        file_path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("ValidationHistoryStore recorded run history entry: %s", file_path)
        return file_path
