"""
Ray Casting and Geometry Mathematics Engine.

Provides high-performance vector/geometric algorithms:
- Ray casting point-in-polygon containment test
- AABB pre-filtering
- Polygon/Edge intersection test
- Point to line segment closest distance & closest edge calculation
- Polygons area, centroid, orientation, and edge precomputation
"""

from __future__ import annotations

import math
from typing import Optional, Sequence, Tuple

from camera_analytics.core.spatial.models import (
    BoundingBox2D,
    Edge2D,
    PixelPoint,
    PolygonOrientation,
)


class RayCastingEngine:
    """High-performance 2D Spatial Geometry Mathematics Engine."""

    @staticmethod
    def point_in_polygon(point: PixelPoint, polygon: Sequence[PixelPoint]) -> bool:
        """Ray Casting algorithm (Even-Odd Winding Number Rule) for point-in-polygon inclusion.

        Crosses horizontal ray from `point` towards positive infinity X.
        Counts how many polygon edges intersect the ray. Odd = inside, Even = outside.

        Args:
            point: Target PixelPoint to query.
            polygon: Ordered sequence of vertices defining closed polygon.

        Returns:
            True if point is strictly inside or on edge of polygon; False otherwise.
        """
        n = len(polygon)
        if n < 3:
            return False

        px, py = point.x, point.y
        inside = False

        j = n - 1
        for i in range(n):
            vi = polygon[i]
            vj = polygon[j]

            ix, iy = vi.x, vi.y
            jx, jy = vj.x, vj.y

            # Ray casting intersection condition
            if ((iy > py) != (jy > py)):
                # Calculate exact X intersection coordinate of edge with horizontal line Y = py
                intersect_x = (jx - ix) * (py - iy) / float(jy - iy + 1e-12) + ix
                if px < intersect_x:
                    inside = not inside

            j = i

        return inside

    @staticmethod
    def point_in_zone(point: PixelPoint, bbox: BoundingBox2D, polygon: Sequence[PixelPoint]) -> bool:
        """Optimized point inclusion test with AABB pre-filtering.

        Args:
            point: Target point.
            bbox: Precomputed Axis-Aligned Bounding Box.
            polygon: Polygon vertices.

        Returns:
            True if point is inside polygon, False otherwise.
        """
        # Fast bounding box rejection check
        if not bbox.contains_point(point):
            return False

        return RayCastingEngine.point_in_polygon(point, polygon)

    @staticmethod
    def distance_point_to_segment(point: PixelPoint, edge: Edge2D) -> Tuple[float, PixelPoint]:
        """Calculate shortest distance from point to a 2D line segment and return projection point.

        Args:
            point: Query pixel point.
            edge: Line segment (p1 -> p2).

        Returns:
            Tuple of (shortest_distance, closest_pixel_point_on_segment).
        """
        px, py = point.x, point.y
        x1, y1 = edge.p1.x, edge.p1.y
        x2, y2 = edge.p2.x, edge.p2.y

        dx = x2 - x1
        dy = y2 - y1

        if dx == 0 and dy == 0:
            dist = edge.p1.distance_to(point)
            return dist, edge.p1

        # Project point onto line vector, normalized t in [0, 1]
        t = ((px - x1) * dx + (py - y1) * dy) / float(dx * dx + dy * dy)

        if t <= 0.0:
            proj = edge.p1
        elif t >= 1.0:
            proj = edge.p2
        else:
            proj = PixelPoint(x=int(round(x1 + t * dx)), y=int(round(y1 + t * dy)))

        dist = proj.distance_to(point)
        return dist, proj

    @staticmethod
    def closest_edge(point: PixelPoint, edges: Sequence[Edge2D]) -> Tuple[Optional[Edge2D], float, PixelPoint]:
        """Find the closest edge in a polygon to a given point.

        Args:
            point: Query point.
            edges: Sequence of precomputed edges.

        Returns:
            Tuple of (closest_edge, min_distance, projection_point).
        """
        if not edges:
            return None, float("inf"), point

        min_dist = float("inf")
        best_edge: Optional[Edge2D] = None
        best_proj = point

        for edge in edges:
            dist, proj = RayCastingEngine.distance_point_to_segment(point, edge)
            if dist < min_dist:
                min_dist = dist
                best_edge = edge
                best_proj = proj

        return best_edge, min_dist, best_proj

    @staticmethod
    def segments_intersect(seg1: Edge2D, seg2: Edge2D) -> bool:
        """Check if two line segments intersect using cross-product orientation test."""
        def ccw(a: PixelPoint, b: PixelPoint, c: PixelPoint) -> float:
            return (c.y - a.y) * (b.x - a.x) - (b.y - a.y) * (c.x - a.x)

        p1, p2 = seg1.p1, seg1.p2
        p3, p4 = seg2.p1, seg2.p2

        return (
            (ccw(p1, p3, p4) * ccw(p2, p3, p4) <= 0)
            and (ccw(p1, p2, p3) * ccw(p1, p2, p4) <= 0)
        )


class GeometryUtils:
    """Utility methods for precomputing polygon bounding boxes, centroids, area, edges, and winding."""

    @staticmethod
    def compute_bounding_box(polygon: Sequence[PixelPoint]) -> BoundingBox2D:
        """Compute Axis-Aligned Bounding Box (AABB) for a polygon."""
        if not polygon:
            return BoundingBox2D(0, 0, 0, 0)

        min_x = min(p.x for p in polygon)
        min_y = min(p.y for p in polygon)
        max_x = max(p.x for p in polygon)
        max_y = max(p.y for p in polygon)

        return BoundingBox2D(min_x=min_x, min_y=min_y, max_x=max_x, max_y=max_y)

    @staticmethod
    def compute_area_and_centroid(polygon: Sequence[PixelPoint]) -> Tuple[float, PixelPoint, PolygonOrientation]:
        """Compute polygon Area (Shoelace Formula), Centroid, and Winding Orientation."""
        n = len(polygon)
        if n < 3:
            if n == 0:
                return 0.0, PixelPoint(0, 0), PolygonOrientation.DEGENERATE
            avg_x = int(sum(p.x for p in polygon) / n)
            avg_y = int(sum(p.y for p in polygon) / n)
            return 0.0, PixelPoint(avg_x, avg_y), PolygonOrientation.DEGENERATE

        signed_area = 0.0
        cx = 0.0
        cy = 0.0

        j = n - 1
        for i in range(n):
            p0 = polygon[j]
            p1 = polygon[i]

            cross = p0.x * p1.y - p1.x * p0.y
            signed_area += cross
            cx += (p0.x + p1.x) * cross
            cy += (p0.y + p1.y) * cross

            j = i

        signed_area *= 0.5
        abs_area = abs(signed_area)

        if abs_area < 1e-6:
            avg_x = int(sum(p.x for p in polygon) / n)
            avg_y = int(sum(p.y for p in polygon) / n)
            return 0.0, PixelPoint(avg_x, avg_y), PolygonOrientation.DEGENERATE

        centroid_x = int(round(cx / (6.0 * signed_area)))
        centroid_y = int(round(cy / (6.0 * signed_area)))

        orientation = (
            PolygonOrientation.CLOCKWISE
            if signed_area < 0
            else PolygonOrientation.COUNTER_CLOCKWISE
        )

        return abs_area, PixelPoint(centroid_x, centroid_y), orientation

    @staticmethod
    def compute_edges(polygon: Sequence[PixelPoint]) -> list[Edge2D]:
        """Build list of Edge2D line segments from ordered polygon vertices."""
        n = len(polygon)
        if n < 2:
            return []

        edges: list[Edge2D] = []
        for i in range(n):
            p1 = polygon[i]
            p2 = polygon[(i + 1) % n]
            edges.append(Edge2D(p1=p1, p2=p2))

        return edges
