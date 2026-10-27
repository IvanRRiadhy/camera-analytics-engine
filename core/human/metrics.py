"""
Human Runtime Metrics API Infrastructure (Sprint H1.4.7).

Provides model-agnostic operational telemetry endpoints for real-time dashboards and diagnostics,
reporting scheduler quality gate statistics, queue waiting time, and latency percentiles.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional
from camera_analytics.core.human.profiler import InferenceProfiler
from camera_analytics.core.human.scheduler import HumanAnalyticsScheduler

logger = logging.getLogger(__name__)


class HumanRuntimeMetrics:
    """Standardized API provider for Human Runtime operational metrics."""

    def __init__(self, scheduler: Optional[HumanAnalyticsScheduler] = None, profiler: Optional[InferenceProfiler] = None) -> None:
        self.scheduler = scheduler
        self.profiler = profiler or (scheduler.profiler if scheduler else InferenceProfiler())

    def get_runtime_telemetry(self) -> dict[str, Any]:
        """Return comprehensive operational telemetry snapshot for dashboards."""
        scheduler_summary = self.scheduler.get_metrics_summary() if self.scheduler else {}
        profiler_summary = self.profiler.get_all_profiles()

        return {
            "timestamp": time.time(),
            "scheduler": {
                "activeModules": len(scheduler_summary),
                "modules": scheduler_summary,
            },
            "profiler": {
                "totalModulesTracked": len(profiler_summary),
                "profiles": profiler_summary,
            },
            "status": "HEALTHY",
        }
