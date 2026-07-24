"""
Domain Entity Models Package.

Provides standardized, strongly typed domain representations of all AI detection outputs,
tracking objects, spatial zones, pose keypoints, and camera runtime contexts.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from camera_analytics.core.track_features import TrackFeatureStore


class GroundPointSource(Enum):
    """Source origin of ground point estimation."""

    ANKLE = "ANKLE"
    KNEE = "KNEE"
    HIP = "HIP"
    BBOX = "BBOX"


class ZoneState(Enum):
    """Spatial relationship state of a track relative to a zone."""

    OUTSIDE = "OUTSIDE"
    ENTER = "ENTER"
    INSIDE = "INSIDE"
    EXIT = "EXIT"


@dataclass(frozen=True, slots=True)
class BoundingBoxEntity:
    """Bounding Box domain representation in pixel coordinates."""

    x1: int
    y1: int
    x2: int
    y2: int

    @property
    def width(self) -> int:
        """Width of bounding box in pixels."""
        return self.x2 - self.x1

    @property
    def height(self) -> int:
        """Height of bounding box in pixels."""
        return self.y2 - self.y1

    @property
    def area(self) -> int:
        """Area of bounding box in square pixels."""
        return self.width * self.height

    @property
    def center(self) -> tuple[int, int]:
        """Center coordinate (x, y) in pixels."""
        return (self.x1 + self.width // 2, self.y1 + self.height // 2)

    def to_dict(self) -> dict[str, int]:
        """Convert BoundingBox to dictionary."""
        return {
            "x1": self.x1,
            "y1": self.y1,
            "x2": self.x2,
            "y2": self.y2,
            "width": self.width,
            "height": self.height,
            "center_x": self.center[0],
            "center_y": self.center[1],
            "area": self.area,
        }


@dataclass(frozen=True, slots=True)
class GroundPointEntity:
    """Ground Point (foot contact position) domain representation."""

    x: int
    y: int
    source: GroundPointSource = GroundPointSource.BBOX

    def to_dict(self) -> dict[str, Any]:
        """Convert GroundPoint to dictionary."""
        return {"x": self.x, "y": self.y, "source": self.source.value}


@dataclass(frozen=True, slots=True)
class VelocityEntity:
    """Velocity vector domain representation."""

    vx: float = 0.0
    vy: float = 0.0

    @property
    def speed(self) -> float:
        """Magnitude speed in pixels per second/frame."""
        return math.sqrt(self.vx ** 2 + self.vy ** 2)

    def to_dict(self) -> dict[str, float]:
        """Convert Velocity to dictionary."""
        return {"vx": round(self.vx, 2), "vy": round(self.vy, 2), "speed": round(self.speed, 2)}


@dataclass(frozen=True, slots=True)
class DirectionEntity:
    """Movement direction domain representation."""

    heading_degrees: float = 0.0
    cardinal_direction: str = "N"

    def to_dict(self) -> dict[str, Any]:
        """Convert Direction to dictionary."""
        return {
            "heading_degrees": round(self.heading_degrees, 1),
            "cardinal_direction": self.cardinal_direction,
        }


@dataclass(frozen=True, slots=True)
class KeypointEntity:
    """Keypoint domain representation."""

    index: int
    name: str
    x: float
    y: float
    confidence: float

    @property
    def is_visible(self) -> bool:
        """Whether keypoint is visible."""
        return self.confidence >= 0.5


@dataclass(frozen=True, slots=True)
class PoseEntity:
    """COCO 17-Keypoint Pose domain representation."""

    keypoints: list[KeypointEntity] = field(default_factory=list)
    confidence: float = 0.0

    @property
    def visible_points_count(self) -> int:
        """Count of keypoints with confidence >= 0.5."""
        return sum(1 for kp in self.keypoints if kp.is_visible)

    def to_dict(self) -> dict[str, Any]:
        """Convert Pose to dictionary."""
        return {
            "confidence": round(self.confidence, 2),
            "visible_points_count": self.visible_points_count,
            "keypoints": [
                {
                    "index": kp.index,
                    "name": kp.name,
                    "x": round(kp.x, 1),
                    "y": round(kp.y, 1),
                    "confidence": round(kp.confidence, 2),
                }
                for kp in self.keypoints
            ],
        }


@dataclass(frozen=True, slots=True)
class ZoneEntity:
    """Spatial Zone domain representation."""

    zone_id: str
    zone_name: str
    zone_type: str = "region"
    current_state: ZoneState = ZoneState.OUTSIDE
    dwell_frames: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert ZoneEntity to dictionary."""
        return {
            "zone_id": self.zone_id,
            "zone_name": self.zone_name,
            "zone_type": self.zone_type,
            "current_state": self.current_state.value,
            "dwell_frames": self.dwell_frames,
        }


@dataclass(slots=True)
class TrackEntity:
    """Track domain entity representing a persistent tracked human object."""

    track_id: int
    track_age: int = 1
    track_state: str = "CONFIRMED"
    confidence: float = 0.0
    global_id: Optional[int] = None
    bbox: Optional[BoundingBoxEntity] = None
    ground_point: Optional[GroundPointEntity] = None
    velocity: VelocityEntity = field(default_factory=VelocityEntity)
    direction: DirectionEntity = field(default_factory=DirectionEntity)
    pose: Optional[PoseEntity] = None
    feature_store: Optional[TrackFeatureStore] = field(default=None, repr=False)

    def to_dict(self) -> dict[str, Any]:
        """Convert TrackEntity to dictionary."""
        return {
            "track_id": self.track_id,
            "track_age": self.track_age,
            "track_state": self.track_state,
            "confidence": round(self.confidence, 2),
            "global_id": self.global_id,
            "bbox": self.bbox.to_dict() if self.bbox else None,
            "ground_point": self.ground_point.to_dict() if self.ground_point else None,
            "velocity": self.velocity.to_dict(),
            "direction": self.direction.to_dict(),
            "pose": self.pose.to_dict() if self.pose else None,
        }


@dataclass(frozen=True, slots=True)
class FrameEntity:
    """Video Frame runtime domain context representation."""

    frame_index: int
    timestamp: float
    frame_width: int
    frame_height: int
    fps: float = 30.0
    latency_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert FrameEntity to dictionary."""
        return {
            "frame_index": self.frame_index,
            "timestamp": round(self.timestamp, 3),
            "resolution": [self.frame_width, self.frame_height],
            "fps": round(self.fps, 1),
            "latency_ms": round(self.latency_ms, 2),
        }


@dataclass(frozen=True, slots=True)
class CameraEntity:
    """CCTV Camera domain context representation."""

    camera_id: str
    camera_name: str
    location: str = "Default Location"
    resolution: tuple[int, int] = (1920, 1080)
    fps: float = 30.0

    def to_dict(self) -> dict[str, Any]:
        """Convert CameraEntity to dictionary."""
        return {
            "camera_id": self.camera_id,
            "camera_name": self.camera_name,
            "location": self.location,
            "resolution": list(self.resolution),
            "fps": self.fps,
        }
