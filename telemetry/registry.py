"""
Runtime Metrics Registry Component.

Thread-safe lifecycle registry storing and managing active PipelineMetricsAccumulator
instances per camera pipeline.
"""

from __future__ import annotations

import logging
import threading
from typing import Optional

from camera_analytics.telemetry.accumulator import PipelineMetricsAccumulator

logger = logging.getLogger(__name__)


class RuntimeMetricsRegistry:
    """Thread-safe lifecycle registry managing per-pipeline PipelineMetricsAccumulator instances."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._accumulators: dict[str, PipelineMetricsAccumulator] = {}

    def create_pipeline(
        self,
        pipeline_id: str,
        camera_id: str = "",
        camera_name: str = "",
        queue_capacity: int = 30,
    ) -> PipelineMetricsAccumulator:
        """Create and register a dedicated PipelineMetricsAccumulator for a pipeline.

        Args:
            pipeline_id: Unique pipeline identifier.
            camera_id: Target camera identifier.
            camera_name: Descriptive camera name.
            queue_capacity: Transport queue capacity bound.

        Returns:
            PipelineMetricsAccumulator instance.
        """
        with self._lock:
            if pipeline_id not in self._accumulators:
                self._accumulators[pipeline_id] = PipelineMetricsAccumulator(
                    pipeline_id=pipeline_id,
                    camera_id=camera_id,
                    camera_name=camera_name,
                    queue_capacity=queue_capacity,
                )
            return self._accumulators[pipeline_id]

    def get_accumulator(self, pipeline_id: str) -> Optional[PipelineMetricsAccumulator]:
        """Retrieve the PipelineMetricsAccumulator registered for a pipeline ID.

        Args:
            pipeline_id: Target pipeline identifier.

        Returns:
            PipelineMetricsAccumulator instance or None if not registered.
        """
        with self._lock:
            return self._accumulators.get(pipeline_id)

    def remove_pipeline(self, pipeline_id: str) -> bool:
        """Remove and unregister a pipeline's accumulator.

        Args:
            pipeline_id: Pipeline identifier to remove.

        Returns:
            True if removed, False if not found.
        """
        with self._lock:
            if pipeline_id in self._accumulators:
                del self._accumulators[pipeline_id]
                return True
            return False

    def list_pipeline_ids(self) -> list[str]:
        """List all currently registered pipeline identifiers.

        Returns:
            List of pipeline ID strings.
        """
        with self._lock:
            return list(self._accumulators.keys())

    def clear(self) -> None:
        """Unregister all pipeline accumulators."""
        with self._lock:
            self._accumulators.clear()
