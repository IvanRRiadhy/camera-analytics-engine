"""
Pipeline Health Monitor Component.

Collects pipeline execution health, FPS, latency, memory, and GPU metrics.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from camera_analytics.runtime.analytics.models import PipelineHealthState

logger = logging.getLogger(__name__)


class HealthMonitor:
    """Pipeline-scoped health and metrics collector.

    Reader states supported:
    - CONNECTING: Stream connection initiated or READING with no frames delivered yet.
    - STREAMING: Actively reading and delivering frames within the stall threshold.
    - STALLED: In READING state, but no frames delivered recently (> stalled_after_s).
    - RECONNECTING: Connection lost, stream recovery / reconnect attempts in progress.
    - FAILED: Connection attempts exhausted or fatal stream reader failure.
    - STOPPED: Reader worker shut down or halted.
    - UNKNOWN: Reader worker not available or missing required telemetry attributes.
    """

    def __init__(self, engine_version: str = "1.5.0", stalled_after_s: float = 5.0) -> None:
        self.engine_version = engine_version
        self.stalled_after_s = stalled_after_s

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

        reader_state = "UNKNOWN"
        if worker is not None:
            r_worker = getattr(worker, "reader_worker", None)
            if r_worker is not None and hasattr(r_worker, "state"):
                raw_st = r_worker.state
                st_name = str(getattr(raw_st, "name", raw_st)).upper()
                if st_name in ("READING", "STREAMING"):
                    if not hasattr(r_worker, "last_frame_time"):
                        reader_state = "UNKNOWN"
                    else:
                        lf = r_worker.last_frame_time
                        if lf is None or lf <= 0.0:
                            reader_state = "CONNECTING"
                        elif (time.time() - lf) <= self.stalled_after_s:
                            reader_state = "STREAMING"
                        else:
                            reader_state = "STALLED"
                else:
                    state_map = {
                        "CREATED": "CONNECTING",
                        "INITIALIZED": "CONNECTING",
                        "CONNECTING": "CONNECTING",
                        "RECONNECTING": "RECONNECTING",
                        "FAILED": "FAILED",
                        "STOPPED": "STOPPED",
                    }
                    reader_state = state_map.get(st_name, "UNKNOWN")

        pipeline_state = "UNKNOWN"
        if worker is not None and hasattr(worker, "state"):
            raw_p_st = worker.state
            pipeline_state = str(getattr(raw_p_st, "name", raw_p_st)).upper()

        return PipelineHealthState(
            fps=fps,
            latency_ms=pipe_lat_ms,
            inference_time_ms=det_ms,
            tracker_time_ms=trk_ms,
            frame_count=frame_count,
            status=status,
            engine_version=self.engine_version,
            reader_state=reader_state,
            pipeline_state=pipeline_state,
        )
