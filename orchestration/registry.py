"""
Thread-safe Pipeline Registry Component.

Provides a thread-safe repository storing and indexing PipelineInstance domain objects
by pipeline_id and camera_id.
"""

from __future__ import annotations

import logging
import threading
from typing import Optional

from camera_analytics.orchestration.instance import PipelineInstance

logger = logging.getLogger(__name__)


class PipelineRegistryError(KeyError):
    """Raised when pipeline lookup fails in PipelineRegistry."""


class PipelineRegistry:
    """Thread-safe registry for active PipelineInstance entities.

    Utilizes an RLock to allow thread-safe registration, unregistration, state update,
    and fast $O(1)$ lookups by pipeline_id or camera_id.
    """

    def __init__(self) -> None:
        self._by_pipeline_id: dict[str, PipelineInstance] = {}
        self._by_camera_id: dict[str, PipelineInstance] = {}
        self._lock = threading.RLock()

    def register(self, instance: PipelineInstance) -> None:
        """Register a PipelineInstance in the registry.

        Args:
            instance: PipelineInstance entity.
        """
        with self._lock:
            if instance.pipeline_id in self._by_pipeline_id:
                logger.warning(
                    "PipelineRegistry: Overwriting existing pipeline '%s'", instance.pipeline_id
                )
            self._by_pipeline_id[instance.pipeline_id] = instance
            self._by_camera_id[instance.camera_id] = instance
            logger.debug(
                "PipelineRegistry: Registered pipeline '%s' for camera '%s'",
                instance.pipeline_id,
                instance.camera_id,
            )

    def get(self, pipeline_id: str) -> Optional[PipelineInstance]:
        """Retrieve a PipelineInstance by pipeline_id."""
        with self._lock:
            return self._by_pipeline_id.get(pipeline_id)

    def get_by_camera(self, camera_id: str) -> Optional[PipelineInstance]:
        """Retrieve a PipelineInstance by camera_id."""
        with self._lock:
            return self._by_camera_id.get(camera_id)

    def get_required(self, pipeline_id: str) -> PipelineInstance:
        """Retrieve a PipelineInstance or raise PipelineRegistryError."""
        with self._lock:
            if pipeline_id not in self._by_pipeline_id:
                raise PipelineRegistryError(
                    f"PipelineRegistry: Pipeline with ID '{pipeline_id}' is not registered."
                )
            return self._by_pipeline_id[pipeline_id]

    def list_all(self) -> list[PipelineInstance]:
        """Return a snapshot list of all registered pipeline instances."""
        with self._lock:
            return list(self._by_pipeline_id.values())

    def unregister(self, pipeline_id: str) -> bool:
        """Remove a pipeline from the registry."""
        with self._lock:
            instance = self._by_pipeline_id.get(pipeline_id)
            if instance is None:
                return False

            del self._by_pipeline_id[pipeline_id]
            if instance.camera_id in self._by_camera_id:
                del self._by_camera_id[instance.camera_id]
            return True

    def clear(self) -> None:
        """Clear all registered pipelines."""
        with self._lock:
            self._by_pipeline_id.clear()
            self._by_camera_id.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._by_pipeline_id)
