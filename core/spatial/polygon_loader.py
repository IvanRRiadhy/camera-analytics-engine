"""
Polygon Loader and Precomputation Factory.

Parses polygon JSON or raw point list structures, validates spatial geometry,
converts normalized points to pixel space, and instantiates IGeometry objects.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Sequence

from camera_analytics.core.spatial.coordinate_transform import (
    CoordinateTransformEngine,
)
from camera_analytics.core.spatial.geometry import (
    CircleGeometry,
    LineGeometry,
    PolygonGeometry,
)
from camera_analytics.core.spatial.models import (
    PixelPoint,
    Point2D,
    ZoneModel,
    ZoneType,
)
from camera_analytics.core.spatial.raycasting import GeometryUtils

logger = logging.getLogger(__name__)


class PolygonLoader:
    """Polygon Loader and Precomputation Factory for Backend Payloads."""

    @staticmethod
    def parse_points(raw_points: Any) -> list[Point2D]:
        if isinstance(raw_points, str):
            try:
                raw_points = json.loads(raw_points)
            except Exception as exc:
                logger.error("[!] PolygonLoader: Failed to parse JSON string: %s", exc)
                return []

        if not isinstance(raw_points, (list, tuple)):
            return []

        points: list[Point2D] = []
        for item in raw_points:
            if isinstance(item, dict) and "x" in item and "y" in item:
                points.append(Point2D(x=float(item["x"]), y=float(item["y"])))
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                points.append(Point2D(x=float(item[0]), y=float(item[1])))

        return points

    @staticmethod
    def load_zone(
        zone_id: str,
        name: str,
        raw_polygon: Any,
        zone_type: ZoneType = ZoneType.REGION,
        enabled: bool = True,
        color: tuple[int, int, int] = (0, 255, 0),
        metadata: dict[str, Any] | None = None,
        transform_engine: CoordinateTransformEngine | None = None,
    ) -> ZoneModel:
        if transform_engine is None:
            transform_engine = CoordinateTransformEngine(1920, 1080)

        normalized_points = PolygonLoader.parse_points(raw_polygon)
        metadata_dict = metadata or {}

        if zone_type == ZoneType.FULL_FRAME or (not normalized_points and zone_type == ZoneType.FULL_FRAME):
            normalized_points = [
                Point2D(0.0, 0.0),
                Point2D(1.0, 0.0),
                Point2D(1.0, 1.0),
                Point2D(0.0, 1.0),
            ]

        # Auto-detect whether input points are in Pixel Space (x > 1.0 or y > 1.0)
        is_pixel_space = any(pt.x > 1.0 or pt.y > 1.0 for pt in normalized_points)
        if is_pixel_space:
            pixel_polygon = [PixelPoint(x=int(round(pt.x)), y=int(round(pt.y))) for pt in normalized_points]
            normalized_points = [transform_engine.pixel_to_normalized_point(pt) for pt in pixel_polygon]
        else:
            pixel_polygon = transform_engine.normalized_to_pixel_polygon(normalized_points)

        # Instantiate concrete IGeometry implementation
        if zone_type == ZoneType.LINE and len(pixel_polygon) >= 2:
            geometry = LineGeometry(pixel_polygon[0], pixel_polygon[1])
        elif zone_type == ZoneType.CIRCLE and len(pixel_polygon) >= 1:
            geometry = CircleGeometry(pixel_polygon[0], radius_pixels=50.0)
        else:
            geometry = PolygonGeometry(pixel_polygon)

        bbox = geometry.bounding_box()
        area = geometry.area()
        centroid = geometry.centroid()
        edges = geometry.edges()

        zone = ZoneModel(
            id=zone_id,
            name=name,
            type=zone_type,
            enabled=enabled,
            polygon_normalized=normalized_points,
            polygon_pixels=pixel_polygon,
            geometry=geometry,
            bounding_box=bbox,
            centroid=centroid,
            area=area,
            edges=edges,
            color=color,
            metadata=metadata_dict,
            frame_resolution=transform_engine.resolution,
        )

        return zone

    @staticmethod
    def recompute_zone(
        zone: ZoneModel, transform_engine: CoordinateTransformEngine
    ) -> ZoneModel:
        return PolygonLoader.load_zone(
            zone_id=zone.id,
            name=zone.name,
            raw_polygon=zone.polygon_normalized,
            zone_type=zone.type,
            enabled=zone.enabled,
            color=zone.color,
            metadata=zone.metadata,
            transform_engine=transform_engine,
        )
