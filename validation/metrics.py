"""
Analytics Metrics Engine.

Computes Precision, Recall, F1 Score, Accuracy, False Positives (FP), False Negatives (FN),
Detection Latency, and Resource Utilization across modules and dataset tags.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from camera_analytics.validation.schema import (
    AnalyticsModuleMetrics,
    EventMatchResult,
    MatchStatus,
    SystemResourceMetrics,
)

logger = logging.getLogger(__name__)


class AnalyticsMetricsEngine:
    """Metrics Engine calculating performance metrics from comparison results."""

    @classmethod
    def compute_metrics(
        cls,
        match_results: list[EventMatchResult],
        resource_metrics: Optional[SystemResourceMetrics] = None,
    ) -> dict[str, Any]:
        """Compute overall and per-event-type accuracy metrics.

        Args:
            match_results: List of EventMatchResult instances.
            resource_metrics: System resource and throughput metrics.

        Returns:
            Dictionary containing overall metrics, breakdown per event_type/module, and resources.
        """
        overall = AnalyticsModuleMetrics()
        type_breakdown: dict[str, AnalyticsModuleMetrics] = {}
        delays_ms: list[float] = []

        for r in match_results:
            evt_type = (
                r.ground_truth.event_type
                if r.ground_truth
                else (r.generated_event.get("event_type", "UNKNOWN") if r.generated_event else "UNKNOWN")
            )

            if evt_type not in type_breakdown:
                type_breakdown[evt_type] = AnalyticsModuleMetrics()

            mod_m = type_breakdown[evt_type]

            if r.status == MatchStatus.TRUE_POSITIVE:
                overall.true_positives += 1
                mod_m.true_positives += 1
                delays_ms.append(r.detection_delay_seconds * 1000.0)
            elif r.status == MatchStatus.FALSE_POSITIVE:
                overall.false_positives += 1
                mod_m.false_positives += 1
            elif r.status == MatchStatus.FALSE_NEGATIVE:
                overall.false_negatives += 1
                mod_m.false_negatives += 1

        # Compute overall stats
        overall.avg_detection_delay_ms = sum(delays_ms) / max(1, len(delays_ms))
        overall.calculate()

        # Compute module stats
        per_type_dict = {}
        for evt_type, mod_m in type_breakdown.items():
            mod_m.calculate()
            per_type_dict[evt_type] = mod_m.to_dict()

        res_dict = resource_metrics.to_dict() if resource_metrics else SystemResourceMetrics().to_dict()

        return {
            "overall": overall.to_dict(),
            "by_event_type": per_type_dict,
            "resources": res_dict,
        }
