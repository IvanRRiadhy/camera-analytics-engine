"""
People Counting Analytics Plugin.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from camera_analytics.context.unified_context import SharedAnalyticsContext
from camera_analytics.events.models import BaseRuntimeEvent, CountingEvent
from camera_analytics.sdk.base_plugin import BaseAnalyticsPlugin

logger = logging.getLogger(__name__)


class PeopleCountingPlugin(BaseAnalyticsPlugin):
    """Realtime bidirectional people counting & occupancy analytics plugin."""

    def __init__(self, name: str = "People Counting", version: str = "1.0.0") -> None:
        super().__init__(name=name, version=version, description="Realtime bidirectional people counting analytics.")
        self.total_in = 0
        self.total_out = 0
        self._last_published_in = -1
        self._last_published_out = -1

    def process(self, context: SharedAnalyticsContext) -> list[BaseRuntimeEvent]:
        """Process pre-computed tracks & detections from SharedAnalyticsContext."""
        start_t = time.perf_counter()

        person_count = context.active_person_count
        self.total_in = max(self.total_in, person_count)

        # Update PluginStateRepository with strongly typed PeopleCountingState
        if hasattr(context, "plugin_repository") and context.plugin_repository is not None:
            from camera_analytics.runtime.analytics.models import PeopleCountingState
            st = PeopleCountingState(
                current=person_count,
                entered=self.total_in,
                exited=self.total_out,
            )
            context.plugin_repository.update_state("peopleCounting", st)

            # Record per-zone breakdown for enterprise Contract V2
            if hasattr(context, "zone_results") and isinstance(context.zone_results, dict):
                counts = context.zone_results.get("zone_counts", {})
                if isinstance(counts, dict):
                    for z_id, z_count in counts.items():
                        context.plugin_repository.update_zone_metric(
                            "peopleCounting", z_id, {"current": z_count, "entered": z_count, "exited": 0}
                        )

        elapsed_ms = (time.perf_counter() - start_t) * 1000.0
        self.last_inference_time_ms = elapsed_ms
        self.total_inference_time_ms += elapsed_ms

        return []
