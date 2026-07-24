"""
Camera data models.

Represents a camera source and its configuration. Each camera has
a unique identity, video source URI, resolution info, and a collection
of zones that define regions of interest within its field of view.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

from camera_analytics.models.zone import Zone


class CameraStatus(Enum):
    """Operational status of a camera.

    Attributes:
        OFFLINE: Camera is not connected or not streaming.
        ONLINE: Camera is actively streaming and available.
        ERROR: Camera encountered an error (e.g., connection lost).
        PAUSED: Camera stream is intentionally paused.
    """

    OFFLINE = auto()
    ONLINE = auto()
    ERROR = auto()
    PAUSED = auto()


@dataclass(slots=True)
class Camera:
    """Configuration and state of a single camera source.

    Encapsulates everything needed to connect to a video source,
    process its frames, and define the spatial regions of interest
    for analytics modules.

    Attributes:
        camera_id: Unique identifier for this camera.
        name: Human-readable display name.
        source: Video source URI (RTSP URL, file path, or device index).
        width: Frame width in pixels (0 if unknown until first frame).
        height: Frame height in pixels (0 if unknown until first frame).
        fps: Frames per second (0.0 if unknown until first frame).
        zones: Dictionary of zones keyed by zone_id.
        status: Current operational status.
        description: Optional description of camera location or purpose.
        metadata: Arbitrary key-value data for integration-specific config.
    """

    camera_id: str
    name: str
    source: str
    width: int = 0
    height: int = 0
    fps: float = 0.0
    zones: dict[str, Zone] = field(default_factory=dict)
    status: CameraStatus = CameraStatus.OFFLINE
    description: str = ""
    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def resolution(self) -> tuple[int, int]:
        """Frame resolution as (width, height) tuple."""
        return (self.width, self.height)

    @property
    def is_online(self) -> bool:
        """Whether the camera is currently online."""
        return self.status == CameraStatus.ONLINE

    @property
    def has_zones(self) -> bool:
        """Whether any zones are defined for this camera."""
        return len(self.zones) > 0

    def add_zone(self, zone: Zone) -> None:
        """Register a zone for this camera.

        Args:
            zone: The zone to add.

        Raises:
            ValueError: If a zone with the same zone_id already exists.
        """
        if zone.zone_id in self.zones:
            raise ValueError(
                f"Zone '{zone.zone_id}' already exists on camera "
                f"'{self.camera_id}'."
            )
        self.zones[zone.zone_id] = zone

    def remove_zone(self, zone_id: str) -> Optional[Zone]:
        """Remove a zone by its ID.

        Args:
            zone_id: The ID of the zone to remove.

        Returns:
            The removed Zone, or None if not found.
        """
        return self.zones.pop(zone_id, None)

    def get_zone(self, zone_id: str) -> Optional[Zone]:
        """Retrieve a zone by its ID.

        Args:
            zone_id: The ID of the zone to look up.

        Returns:
            The Zone if found, or None.
        """
        return self.zones.get(zone_id)

    def update_resolution(self, width: int, height: int, fps: float) -> None:
        """Update camera resolution info (typically from first frame).

        Args:
            width: Frame width in pixels.
            height: Frame height in pixels.
            fps: Frames per second.
        """
        self.width = width
        self.height = height
        self.fps = fps

    def set_online(self) -> None:
        """Set camera status to ONLINE."""
        self.status = CameraStatus.ONLINE

    def set_offline(self) -> None:
        """Set camera status to OFFLINE."""
        self.status = CameraStatus.OFFLINE

    def set_error(self) -> None:
        """Set camera status to ERROR."""
        self.status = CameraStatus.ERROR

    def set_paused(self) -> None:
        """Set camera status to PAUSED."""
        self.status = CameraStatus.PAUSED
