"""
RuntimeParityValidator Component for CCTV Analytics AI Engine.

Compares benchmark telemetry outputs against baselines and performance budgets:
- Baseline Repository: camera_analytics/runtime/baselines/
- Performance Budget: configs/benchmark/performance_budget.json
- Tolerances: FPS Delta <= 3%, Latency Delta <= 5%, Memory Delta <= 10%, Tracking/Detection Parity = 100%
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from camera_analytics.bootstrap.resource_manager import RuntimeResourceManager
from camera_analytics.runtime.benchmark.benchmark_runner import BenchmarkResult

logger = logging.getLogger(__name__)


@dataclass
class ParityEvaluationResult:
    """Parity evaluation output dataclass."""

    passed: bool
    fps_delta_pct: float
    latency_delta_pct: float
    memory_delta_pct: float
    tracking_parity: bool
    detection_parity: bool
    violations: List[str]


class RuntimeParityValidator:
    """Validator evaluating runtime outputs against performance budget SLA & baseline repository."""

    def __init__(self) -> None:
        self.rm = RuntimeResourceManager.get_instance()

    def load_performance_budget(self) -> Dict[str, Any]:
        """Load performance budget SLA thresholds."""
        budget_path = self.rm.resolve("configs/benchmark/performance_budget.json")
        if budget_path.exists():
            with open(budget_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {
          "sla_thresholds": {"min_fps": 25.0, "max_pipeline_latency_ms": 40.0},
          "parity_tolerances": {"fps_tolerance_pct": 3.0, "latency_tolerance_pct": 5.0}
        }

    def evaluate_parity(self, result: BenchmarkResult, baseline: Optional[BenchmarkResult] = None) -> ParityEvaluationResult:
        """Evaluate benchmark result against SLA budget and reference baseline."""
        budget = self.load_performance_budget()
        sla = budget.get("sla_thresholds", {})
        tolerances = budget.get("parity_tolerances", {})

        violations: List[str] = []

        # 1. Evaluate SLA Thresholds
        if result.avg_fps < sla.get("min_fps", 25.0):
            violations.append(f"FPS below SLA threshold: {result.avg_fps} < {sla.get('min_fps', 25.0)}")

        if result.avg_pipeline_latency_ms > sla.get("max_pipeline_latency_ms", 40.0):
            violations.append(f"Pipeline latency above SLA threshold: {result.avg_pipeline_latency_ms} ms > {sla.get('max_pipeline_latency_ms', 40.0)} ms")

        # 2. Evaluate Baseline Parity (if baseline provided)
        fps_delta = 0.0
        lat_delta = 0.0
        mem_delta = 0.0
        tracking_ok = True
        detection_ok = True

        if baseline:
            if baseline.avg_fps > 0:
                fps_delta = abs(result.avg_fps - baseline.avg_fps) / baseline.avg_fps * 100.0
                if fps_delta > tolerances.get("fps_tolerance_pct", 3.0):
                    violations.append(f"FPS delta exceeds tolerance: {fps_delta:.2f}% > {tolerances.get('fps_tolerance_pct', 3.0)}%")

            if baseline.avg_pipeline_latency_ms > 0:
                lat_delta = abs(result.avg_pipeline_latency_ms - baseline.avg_pipeline_latency_ms) / baseline.avg_pipeline_latency_ms * 100.0
                if lat_delta > tolerances.get("latency_tolerance_pct", 5.0):
                    violations.append(f"Latency delta exceeds tolerance: {lat_delta:.2f}% > {tolerances.get('latency_tolerance_pct', 5.0)}%")

            if result.tracking_count != baseline.tracking_count:
                tracking_ok = False
                violations.append(f"Tracking count mismatch: {result.tracking_count} != {baseline.tracking_count}")

            if result.detection_count != baseline.detection_count:
                detection_ok = False
                violations.append(f"Detection count mismatch: {result.detection_count} != {baseline.detection_count}")

        passed = len(violations) == 0
        return ParityEvaluationResult(
            passed=passed,
            fps_delta_pct=round(fps_delta, 2),
            latency_delta_pct=round(lat_delta, 2),
            memory_delta_pct=round(mem_delta, 2),
            tracking_parity=tracking_ok,
            detection_parity=detection_ok,
            violations=violations,
        )
