"""
Enriched Spatial Geometry Models.

Extends ZoneModel to consume IGeometry, and introduces TrackSpatialState,
ZoneTransitionEvent, and FrameSpatialSnapshot for complete decoupled spatial analytics.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import TYPE_CHECKING, Any, Sequence, Tuple

if TYPE_CHECKING:
    from camera_analytics.core.spatial.geometry import IGeometry


class ZoneType(Enum):
    """Classification of spatial geometry zones."""

    REGION = auto()
    LINE = auto()
    FULL_FRAME = auto()
    CIRCLE = auto()
    MULTI_POLYGON = auto()


class PolygonOrientation(Enum):
    """Winding orientation of a polygon."""

    CLOCKWISE = auto()
    COUNTER_CLOCKWISE = auto()
    DEGENERATE = auto()


class ZoneEventType(Enum):
    """Classification of Zone Engine spatial events."""

    ENTER = auto()
    EXIT = auto()
    STAY = auto()


class GroundPointSource(Enum):
    """Source method for track ground point calculation."""

    ANKLE_MIDPOINT = auto()
    LEFT_ANKLE = auto()
    RIGHT_ANKLE = auto()
    POSE_ANKLES = auto()
    KNEE = auto()
    HIP = auto()
    BBOX_BOTTOM_CENTER = auto()


@dataclass(frozen=True, slots=True)
class Point2D:
    """Float coordinate pair (normalized 0.0-1.0 or float pixel)."""

    x: float
    y: float

    def to_pixel(self, frame_width: int, frame_height: int) -> PixelPoint:
        return PixelPoint(
            x=int(round(self.x * frame_width)),
            y=int(round(self.y * frame_height)),
        )

    def to_tuple(self) -> Tuple[float, float]:
        return (self.x, self.y)


@dataclass(frozen=True, slots=True)
class PixelPoint:
    """2D Integer pixel coordinate."""

    x: int
    y: int

    def distance_to(self, other: PixelPoint) -> float:
        return math.hypot(self.x - other.x, self.y - other.y)

    def to_normalized(self, frame_width: int, frame_height: int) -> Point2D:
        w = max(1, frame_width)
        h = max(1, frame_height)
        return Point2D(x=self.x / w, y=self.y / h)

    def to_tuple(self) -> Tuple[int, int]:
        return (self.x, self.y)


@dataclass(frozen=True, slots=True)
class BoundingBox2D:
    """Axis-Aligned Bounding Box (AABB) in pixel space."""

    min_x: int
    min_y: int
    max_x: int
    max_y: int

    @property
    def width(self) -> int:
        return max(0, self.max_x - self.min_x)

    @property
    def height(self) -> int:
        return max(0, self.max_y - self.min_y)

    @property
    def area(self) -> int:
        return self.width * self.height

    @property
    def center(self) -> PixelPoint:
        return PixelPoint(
            x=(self.min_x + self.max_x) // 2,
            y=(self.min_y + self.max_y) // 2,
        )

    def contains_point(self, point: PixelPoint) -> bool:
        return (
            self.min_x <= point.x <= self.max_x
            and self.min_y <= point.y <= self.max_y
        )

    def intersects(self, other: BoundingBox2D) -> bool:
        return not (
            self.max_x < other.min_x
            or self.min_x > other.max_x
            or self.max_y < other.min_y
            or self.min_y > other.max_y
        )


@dataclass(frozen=True, slots=True)
class Edge2D:
    """Line segment connecting two PixelPoints."""

    p1: PixelPoint
    p2: PixelPoint

    @property
    def length(self) -> float:
        return self.p1.distance_to(self.p2)

    def midpoint(self) -> PixelPoint:
        return PixelPoint(
            x=(self.p1.x + self.p2.x) // 2,
            y=(self.p1.y + self.p2.y) // 2,
        )


@dataclass(slots=True)
class ZoneModel:
    """Production Zone Domain Model consuming IGeometry."""

    id: str
    name: str
    type: ZoneType
    enabled: bool
    polygon_normalized: list[Point2D]
    polygon_pixels: list[PixelPoint] = field(default_factory=list)
    geometry: IGeometry | None = None
    bounding_box: BoundingBox2D = field(
        default_factory=lambda: BoundingBox2D(0, 0, 0, 0)
    )
    centroid: PixelPoint = field(default_factory=lambda: PixelPoint(0, 0))
    area: float = 0.0
    orientation: PolygonOrientation = PolygonOrientation.DEGENERATE
    edges: list[Edge2D] = field(default_factory=list)
    color: tuple[int, int, int] = (0, 255, 0)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    frame_resolution: tuple[int, int] = (0, 0)

    def contains_point(self, point: PixelPoint) -> bool:
        if self.type == ZoneType.FULL_FRAME:
            return True
        if self.geometry:
            return self.geometry.contains_point(point)
        return self.bounding_box.contains_point(point)


@dataclass(slots=True)
class TrackSpatialState:
    """High-level spatial tracking state for a single track."""

    track_id: int
    ground_point: PixelPoint
    ground_point_source: GroundPointSource
    active_zone_ids: set[str] = field(default_factory=set)
    zone_dwell_frames: dict[str, int] = field(default_factory=dict)
    zone_entry_timestamps: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ZoneTransitionEvent:
    """Enriched spatial transition event payload for downstream services."""

    event_type: ZoneEventType
    track_id: int
    zone_id: str
    zone_name: str
    ground_point: Tuple[int, int]
    ground_point_source: GroundPointSource
    frame_index: int
    timestamp: float
    dwell_frames: int
    dwell_duration_seconds: float
    camera_id: str
    room_id: str = ""
    floor_id: str = ""
    building_id: str = ""
    site_id: str = ""


@dataclass(slots=True)
class FrameSpatialSnapshot:
    """Immutable per-frame spatial runtime snapshot passed to plugins."""

    frame_index: int
    timestamp: float
    camera_id: str
    active_zones: list[ZoneModel]
    track_states: dict[int, TrackSpatialState]
    events: list[ZoneTransitionEvent]
    occupancy_counts: dict[str, int]
