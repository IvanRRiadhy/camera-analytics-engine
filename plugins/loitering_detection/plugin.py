"""
Loitering Detection Analytics Plugin.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from camera_analytics.context.unified_context import SharedAnalyticsContext
from camera_analytics.events.models import BaseRuntimeEvent, DetectionEvent
from camera_analytics.sdk.base_plugin import BaseAnalyticsPlugin

logger = logging.getLogger(__name__)


class LoiteringDetectionPlugin(BaseAnalyticsPlugin):
    """Detects unauthorized loitering in designated zones."""

    def __init__(self, name: str = "Loitering Detection", version: str = "1.0.0") -> None:
        super().__init__(name=name, version=version, description="Detects unauthorized loitering in designated zones.")
        self._reported_track_ids: set[int] = set()

    def process(self, context: SharedAnalyticsContext) -> list[BaseRuntimeEvent]:
        """Process pre-computed tracks from SharedAnalyticsContext."""
        start_t = time.perf_counter()

        events: list[BaseRuntimeEvent] = []
        snap = getattr(context, "spatial_snapshot", None)
        loitering_track_ids: list[int] = []

        if snap is not None:
            for tid, st in snap.track_states.items():
                for zid, dwell_f in st.zone_dwell_frames.items():
                    if dwell_f > 150:
                        loitering_track_ids.append(tid)

        if hasattr(context, "plugin_repository") and context.plugin_repository is not None:
            from camera_analytics.runtime.analytics.models import LoiteringState
            st = LoiteringState(
                active_count=len(loitering_track_ids),
                track_ids=tuple(loitering_track_ids),
            )
            context.plugin_repository.update_state("loitering", st)

        elapsed_ms = (time.perf_counter() - start_t) * 1000.0
        self.last_inference_time_ms = elapsed_ms
        self.total_inference_time_ms += elapsed_ms

        return events
