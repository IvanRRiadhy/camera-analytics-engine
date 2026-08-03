"""
Camera Catalog Domain Package.

Central manager for camera domain models, stream statuses, and zone mappings.
"""

from __future__ import annotations

import logging
import threading
from typing import Optional

from camera_analytics.models.camera import Camera, CameraStatus

logger = logging.getLogger(__name__)


class CameraCatalogError(Exception):
    """Raised when camera registration or lookup operations fail."""


class CameraCatalog:
    """Central domain repository managing active Camera instances.

    Serves as the single source of truth for Camera metadata, RTSP URIs,
    resolution, status, and zone mappings across all active pipelines.
    Consumed by ExecutionScheduler, Diagnostics, and Pipeline Orchestrator.
    """

    def __init__(self) -> None:
        self._cameras: dict[str, Camera] = {}
        self._lock = threading.Lock()

    def register_camera(self, camera: Camera) -> None:
        """Register a Camera instance in the catalog.

        Args:
            camera: Camera domain model instance.
        """
        with self._lock:
            if camera.camera_id in self._cameras:
                logger.warning(
                    "CameraCatalog: Overwriting camera registration for camera_id '%s'",
                    camera.camera_id,
                )
            self._cameras[camera.camera_id] = camera
            logger.info(
                "CameraCatalog: Registered camera '%s' (ID: %s, URI: %s)",
                camera.name,
                camera.camera_id,
                camera.source,
            )

    def get_camera(self, camera_id: str) -> Optional[Camera]:
        """Retrieve a registered Camera instance by camera_id.

        Args:
            camera_id: Unique string camera identifier.

        Returns:
            Camera object if registered, None otherwise.
        """
        with self._lock:
            return self._cameras.get(camera_id)

    def get_required_camera(self, camera_id: str) -> Camera:
        """Retrieve a registered Camera or raise CameraCatalogError."""
        with self._lock:
            if camera_id not in self._cameras:
                raise CameraCatalogError(
                    f"CameraCatalog: Camera with ID '{camera_id}' is not registered."
                )
            return self._cameras[camera_id]

    def list_cameras(self) -> list[Camera]:
        """Return a snapshot list of all registered cameras."""
        with self._lock:
            return list(self._cameras.values())

    def get_active_cameras(self) -> list[Camera]:
        """Return a list of cameras currently ONLINE."""
        with self._lock:
            return [cam for cam in self._cameras.values() if cam.status == CameraStatus.ONLINE]

    def set_camera_status(self, camera_id: str, status: CameraStatus) -> bool:
        """Update operational status of a camera.

        Args:
            camera_id: Camera identifier string.
            status: Target CameraStatus enum value.

        Returns:
            True if updated, False if camera_id not found.
        """
        with self._lock:
            camera = self._cameras.get(camera_id)
            if camera is None:
                return False
            camera.status = status
            logger.debug("CameraCatalog: Camera '%s' status updated to %s", camera_id, status.name)
            return True

    def unregister_camera(self, camera_id: str) -> bool:
        """Remove a camera from the catalog."""
        with self._lock:
            if camera_id in self._cameras:
                del self._cameras[camera_id]
                return True
            return False

    def clear(self) -> None:
        """Clear all registered cameras."""
        with self._lock:
            self._cameras.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._cameras)
