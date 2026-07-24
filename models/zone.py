"""
Zone data models.

Represents spatial regions of interest (ROI) within a camera frame.
Zones are used by analytics modules to define areas where specific
rules or measurements apply (e.g., restricted areas, counting lines,
dwell-time regions).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

from camera_analytics.models.detection import BoundingBox


class ZoneType(Enum):
    """Classification of zone behavior.

    Attributes:
        REGION: A polygonal area (e.g., restricted zone, dwell area).
        LINE: A crossing line for counting entries/exits.
        FULL_FRAME: The entire camera frame as a single zone.
    """

    REGION = auto()
    LINE = auto()
    FULL_FRAME = auto()


@dataclass(frozen=True, slots=True)
class Point:
    """A 2D point in pixel coordinates.

    Attributes:
        x: X-coordinate in pixels.
        y: Y-coordinate in pixels.
    """

    x: int
    y: int

    def distance_to(self, other: Point) -> float:
        """Euclidean distance to another point.

        Args:
            other: The other point.

        Returns:
            Distance in pixels.
        """
        return ((self.x - other.x) ** 2 + (self.y - other.y) ** 2) ** 0.5


@dataclass(slots=True)
class Zone:
    """A named spatial region within a camera frame.

    Zones define areas of interest for analytics. They can be polygonal
    regions, crossing lines, or the full frame. Analytics modules
    reference zones by name to apply location-specific logic.

    Attributes:
        zone_id: Unique identifier for this zone.
        name: Human-readable name (e.g., 'entrance', 'restricted_area').
        zone_type: The type/behavior of this zone.
        points: Ordered list of vertices defining the zone polygon or line.
        color: Display color as (R, G, B) tuple for visualization.
        metadata: Arbitrary key-value data for module-specific configuration.
    """

    zone_id: str
    name: str
    zone_type: ZoneType
    points: list[Point] = field(default_factory=list)
    color: tuple[int, int, int] = (0, 255, 0)
    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def vertex_count(self) -> int:
        """Number of vertices defining this zone."""
        return len(self.points)

    @property
    def is_valid(self) -> bool:
        """Whether this zone has enough points for its type.

        A LINE requires at least 2 points.
        A REGION requires at least 3 points.
        FULL_FRAME is always valid (no points needed).
        """
        if self.zone_type == ZoneType.FULL_FRAME:
            return True
        if self.zone_type == ZoneType.LINE:
            return len(self.points) >= 2
        return len(self.points) >= 3

    @property
    def as_polygon(self) -> list[tuple[int, int]]:
        """Points as a list of (x, y) tuples (for OpenCV compatibility).

        Returns:
            List of (x, y) coordinate tuples.
        """
        return [(p.x, p.y) for p in self.points]

    def contains_point(self, x: int, y: int) -> bool:
        """Check if a point is inside this zone using ray-casting algorithm.

        Only applicable for REGION and FULL_FRAME zone types.
        For LINE zones, always returns False.

        Args:
            x: X-coordinate to test.
            y: Y-coordinate to test.

        Returns:
            True if the point is inside the zone polygon.
        """
        if self.zone_type == ZoneType.FULL_FRAME:
            return True

        if self.zone_type == ZoneType.LINE:
            return False

        # Ray-casting algorithm for polygon containment
        n = len(self.points)
        if n < 3:
            return False

        inside = False
        j = n - 1
        for i in range(n):
            pi = self.points[i]
            pj = self.points[j]

            if ((pi.y > y) != (pj.y > y)) and (
                x < (pj.x - pi.x) * (y - pi.y) / (pj.y - pi.y) + pi.x
            ):
                inside = not inside
            j = i

        return inside

    def contains_bbox(self, bbox: BoundingBox) -> bool:
        """Check if a bounding box center falls within this zone.

        Args:
            bbox: The bounding box to test.

        Returns:
            True if the bbox center point is inside the zone.
        """
        cx, cy = bbox.center
        return self.contains_point(cx, cy)

    def contains_bbox_overlap(
        self, bbox: BoundingBox, min_ratio: float = 0.5
    ) -> bool:
        """Check if a bounding box overlaps this zone by at least min_ratio.

        Approximated by testing a grid of sample points from the bbox
        against the zone polygon.

        Args:
            bbox: The bounding box to test.
            min_ratio: Minimum fraction of sample points that must be
                       inside the zone (0.0 to 1.0).

        Returns:
            True if the overlap ratio meets or exceeds min_ratio.
        """
        if self.zone_type == ZoneType.FULL_FRAME:
            return True

        # Sample a 3x3 grid within the bounding box
        sample_points: list[tuple[int, int]] = []
        for fy in (0.0, 0.5, 1.0):
            for fx in (0.0, 0.5, 1.0):
                sx = int(bbox.x1 + fx * bbox.width)
                sy = int(bbox.y1 + fy * bbox.height)
                sample_points.append((sx, sy))

        inside_count = sum(
            1 for sx, sy in sample_points if self.contains_point(sx, sy)
        )

        return (inside_count / len(sample_points)) >= min_ratio
