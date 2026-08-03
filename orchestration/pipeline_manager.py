"""
Pipeline Manager Component.

Low-level manager for storing, querying, and updating PipelineInstances.
Does NOT contain high-level orchestration logic (delegated to PipelineCoordinator).
"""

from __future__ import annotations

import logging
from typing import Optional

from camera_analytics.orchestration.instance import PipelineInstance
from camera_analytics.orchestration.registry import PipelineRegistry
from camera_analytics.orchestration.states import PipelineState

logger = logging.getLogger(__name__)


class PipelineManager:
    """Low-level manager responsible for PipelineInstance storage and state mutation delegates."""

    def __init__(self, registry: Optional[PipelineRegistry] = None) -> None:
        self._registry = registry or PipelineRegistry()

    @property
    def registry(self) -> PipelineRegistry:
        """Reference to internal PipelineRegistry."""
        return self._registry

    def add_pipeline(self, instance: PipelineInstance) -> None:
        """Register a PipelineInstance."""
        self._registry.register(instance)

    def remove_pipeline(self, pipeline_id: str) -> bool:
        """Unregister a PipelineInstance."""
        return self._registry.unregister(pipeline_id)

    def get_pipeline(self, pipeline_id: str) -> Optional[PipelineInstance]:
        """Retrieve a pipeline by ID."""
        return self._registry.get(pipeline_id)

    def get_pipeline_by_camera(self, camera_id: str) -> Optional[PipelineInstance]:
        """Retrieve a pipeline by camera ID."""
        return self._registry.get_by_camera(camera_id)

    def update_pipeline_state(
        self,
        pipeline_id: str,
        new_state: PipelineState,
        error_message: Optional[str] = None,
    ) -> Optional[PipelineInstance]:
        """Update and store new state for a pipeline."""
        instance = self._registry.get(pipeline_id)
        if instance is None:
            return None

        updated_instance = instance.with_state(new_state, error_message=error_message)
        self._registry.register(updated_instance)
        logger.debug("PipelineManager: Pipeline '%s' state -> %s", pipeline_id, new_state.name)
        return updated_instance

    def list_pipelines(self) -> list[PipelineInstance]:
        """Snapshot list of all pipelines."""
        return self._registry.list_all()

    def clear(self) -> None:
        """Clear all registered pipelines."""
        self._registry.clear()
