"""
Queue Detection Analytics Plugin.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from camera_analytics.context.unified_context import SharedAnalyticsContext
from camera_analytics.events.models import AlertEvent, BaseRuntimeEvent
from camera_analytics.sdk.base_plugin import BaseAnalyticsPlugin

logger = logging.getLogger(__name__)


class QueueDetectionPlugin(BaseAnalyticsPlugin):
    """Monitors queue lengths, dwell times, and service delays."""

    def __init__(self, name: str = "Queue Detection", version: str = "1.0.0") -> None:
        super().__init__(name=name, version=version, description="Monitors queue lengths and dwell times.")
        self._last_queue_count = -1

    def process(self, context: SharedAnalyticsContext) -> list[BaseRuntimeEvent]:
        """Process pre-computed tracks from SharedAnalyticsContext."""
        start_t = time.perf_counter()

        queue_count = len(context.tracks)
        if context.zone_results and "zone_counts" in context.zone_results:
            counts = context.zone_results["zone_counts"]
            if counts:
                queue_count = max(counts.values())

        if hasattr(context, "plugin_repository") and context.plugin_repository is not None:
            from camera_analytics.runtime.analytics.models import QueueDetectionState
            st = QueueDetectionState(
                queue_length=queue_count,
                waiting_people=queue_count,
            )
            context.plugin_repository.update_state("queueDetection", st)

            # Record per-zone breakdown for enterprise Contract V2
            if hasattr(context, "zone_results") and isinstance(context.zone_results, dict):
                counts = context.zone_results.get("zone_counts", {})
                if isinstance(counts, dict):
                    for z_id, z_count in counts.items():
                        context.plugin_repository.update_zone_metric(
                            "queueDetection", z_id, {"queueLength": z_count, "waitingPeople": z_count}
                        )

        events: list[BaseRuntimeEvent] = []

        elapsed_ms = (time.perf_counter() - start_t) * 1000.0
        self.last_inference_time_ms = elapsed_ms
        self.total_inference_time_ms += elapsed_ms

        return events
