"""
Pipeline Health Monitor Component.

Collects pipeline execution health, FPS, latency, memory, and GPU metrics.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from camera_analytics.runtime.analytics.models import PipelineHealthState

logger = logging.getLogger(__name__)


class HealthMonitor:
    """Pipeline-scoped health and metrics collector."""

    def __init__(self, engine_version: str = "1.5.0") -> None:
        self.engine_version = engine_version

    def collect_health(
        self,
        worker: Optional[Any] = None,
        context: Optional[Any] = None,
    ) -> PipelineHealthState:
        """Collect current execution health state."""
        fps = float(getattr(worker, "fps_execution", 30.0)) if worker else 30.0
        frame_count = int(getattr(worker, "total_processed_frames", getattr(worker, "_total_processed_frames", 0))) if worker else 0

        det_ms = 0.0
        trk_ms = 0.0
        pipe_lat_ms = 0.0

        if context is not None and hasattr(context, "stage_timings_ms"):
            timings = context.stage_timings_ms
            det_ms = float(timings.get("detection_time_ms", 0.0))
            trk_ms = float(timings.get("tracking_time_ms", 0.0))
            pipe_lat_ms = sum(timings.values())

        status = "Running" if (worker and getattr(worker, "_is_running", True)) else "Idle"

        return PipelineHealthState(
            fps=fps,
            latency_ms=pipe_lat_ms,
            inference_time_ms=det_ms,
            tracker_time_ms=trk_ms,
            frame_count=frame_count,
            status=status,
            engine_version=self.engine_version,
        )
