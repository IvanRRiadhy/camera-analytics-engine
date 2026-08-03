"""
Core Geometry Abstraction Interface and Implementations.

Defines unified IGeometry contract, PolygonGeometry, LineGeometry, CircleGeometry,
and RectangleGeometry for seamless spatial containment and precomputation.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Sequence, Tuple

if TYPE_CHECKING:
    from camera_analytics.core.spatial.models import (
        BoundingBox2D,
        Edge2D,
        PixelPoint,
        Point2D,
        PolygonOrientation,
    )
from camera_analytics.core.spatial.raycasting import GeometryUtils, RayCastingEngine


class IGeometry(ABC):
    """Abstract Interface for all 2D Spatial Geometries."""

    @abstractmethod
    def contains_point(self, point: PixelPoint) -> bool:
        """Check if a pixel point is contained within or on boundary of this geometry."""

    @abstractmethod
    def bounding_box(self) -> BoundingBox2D:
        """Axis-Aligned Bounding Box (AABB)."""

    @abstractmethod
    def centroid(self) -> PixelPoint:
        """Geometric centroid pixel point."""

    @abstractmethod
    def area(self) -> float:
        """Surface area in square pixels."""

    @abstractmethod
    def edges(self) -> list[Edge2D]:
        """Sequence of bounding line segment edges."""


class PolygonGeometry(IGeometry):
    """2D Closed Polygon Geometry implementation."""

    def __init__(self, pixel_points: Sequence[PixelPoint]) -> None:
        self._pixels = list(pixel_points)
        self._bbox = GeometryUtils.compute_bounding_box(self._pixels)
        area, centroid, orientation = GeometryUtils.compute_area_and_centroid(self._pixels)
        self._area = area
        self._centroid = centroid
        self._orientation = orientation
        self._edges = GeometryUtils.compute_edges(self._pixels)

    @property
    def pixel_points(self) -> list[PixelPoint]:
        return self._pixels

    def contains_point(self, point: PixelPoint) -> bool:
        return RayCastingEngine.point_in_zone(point, self._bbox, self._pixels)

    def bounding_box(self) -> BoundingBox2D:
        return self._bbox

    def centroid(self) -> PixelPoint:
        return self._centroid

    def area(self) -> float:
        return self._area

    def edges(self) -> list[Edge2D]:
        return self._edges


class LineGeometry(IGeometry):
    """2D Directional Crossing Line Geometry implementation."""

    def __init__(self, p1: PixelPoint, p2: PixelPoint, threshold_pixels: float = 10.0) -> None:
        self.edge = Edge2D(p1, p2)
        self.threshold_pixels = threshold_pixels
        min_x = min(p1.x, p2.x) - int(threshold_pixels)
        min_y = min(p1.y, p2.y) - int(threshold_pixels)
        max_x = max(p1.x, p2.x) + int(threshold_pixels)
        max_y = max(p1.y, p2.y) + int(threshold_pixels)
        self._bbox = BoundingBox2D(min_x, min_y, max_x, max_y)
        self._centroid = self.edge.midpoint()

    def contains_point(self, point: PixelPoint) -> bool:
        if not self._bbox.contains_point(point):
            return False
        dist, _ = RayCastingEngine.distance_point_to_segment(point, self.edge)
        return dist <= self.threshold_pixels

    def bounding_box(self) -> BoundingBox2D:
        return self._bbox

    def centroid(self) -> PixelPoint:
        return self._centroid

    def area(self) -> float:
        return 0.0

    def edges(self) -> list[Edge2D]:
        return [self.edge]


class CircleGeometry(IGeometry):
    """2D Circular Region Geometry implementation."""

    def __init__(self, center: PixelPoint, radius_pixels: float) -> None:
        self._center = center
        self._radius = radius_pixels
        r_int = int(round(radius_pixels))
        self._bbox = BoundingBox2D(
            min_x=center.x - r_int,
            min_y=center.y - r_int,
            max_x=center.x + r_int,
            max_y=center.y + r_int,
        )

    def contains_point(self, point: PixelPoint) -> bool:
        if not self._bbox.contains_point(point):
            return False
        return self._center.distance_to(point) <= self._radius

    def bounding_box(self) -> BoundingBox2D:
        return self._bbox

    def centroid(self) -> PixelPoint:
        return self._center

    def area(self) -> float:
        return math.pi * (self._radius ** 2)

    def edges(self) -> list[Edge2D]:
        return []
