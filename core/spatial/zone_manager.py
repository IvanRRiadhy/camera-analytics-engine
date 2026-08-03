"""
Centralized Spatial Zone Manager.

Owns every spatial ZoneModel across the AI Engine instance. Handles:
- Single-pass loading and precomputation of backend payloads
- Resolution change recomputation
- Thread-safe caching and queries via ISpatialIndex
- Hot reloading without engine restart
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional, Sequence, Tuple

from camera_analytics.core.spatial.cache import SpatialCache
from camera_analytics.core.spatial.coordinate_transform import (
    CoordinateTransformEngine,
)
from camera_analytics.core.spatial.models import (
    BoundingBox2D,
    Edge2D,
    PixelPoint,
    ZoneModel,
    ZoneType,
)
from camera_analytics.core.spatial.polygon_loader import PolygonLoader
from camera_analytics.core.spatial.raycasting import RayCastingEngine

logger = logging.getLogger(__name__)


class ZoneManager:
    """Centralized Enterprise Spatial Zone Manager."""

    def __init__(self, default_resolution: Tuple[int, int] = (1920, 1080)) -> None:
        self._cache = SpatialCache()
        self._transforms: dict[str, CoordinateTransformEngine] = {}
        self._default_resolution = default_resolution

    def _get_transform(self, camera_id: str) -> CoordinateTransformEngine:
        if camera_id not in self._transforms:
            w, h = self._default_resolution
            self._transforms[camera_id] = CoordinateTransformEngine(w, h)
        return self._transforms[camera_id]

    def set_camera_resolution(self, camera_id: str, width: int, height: int) -> None:
        transform = self._get_transform(camera_id)
        if transform.set_resolution(width, height):
            logger.info(
                "[+] ZoneManager: Recomputing spatial zones for camera '%s' at resolution %dx%d...",
                camera_id,
                width,
                height,
            )
            zones = self._cache.get_camera_zones(camera_id)
            for z in zones:
                recomputed = PolygonLoader.recompute_zone(z, transform)
                self._cache.put_zone(camera_id, recomputed)

    def load_zones_from_backend(
        self, camera_id: str, raw_zones_payload: Sequence[dict[str, Any]]
    ) -> List[ZoneModel]:
        transform = self._get_transform(camera_id)
        loaded_zones: List[ZoneModel] = []

        if not raw_zones_payload:
            logger.info("[Spatial] Camera '%s' has 0 configured zones in Backend.", camera_id)
            return []

        logger.info("--------------------------------------------------------------------------------")
        logger.info("[Spatial Engine] Loading %d Zones for Camera '%s'...", len(raw_zones_payload), camera_id)
        logger.info("--------------------------------------------------------------------------------")

        for z_data in raw_zones_payload:
            z_id = str(z_data.get("id") or z_data.get("zoneId") or f"z_{len(loaded_zones)}")
            z_name = str(z_data.get("name", f"Zone {z_id}"))

            # Robust polygon extraction from top-level keys or nested cameraConfigs
            raw_poly = (
                z_data.get("polygonCoordinatesJson")
                or z_data.get("polygon_coordinates_json")
                or z_data.get("polygon")
                or z_data.get("polygonNormalized")
                or z_data.get("points")
            )
            if not raw_poly and "cameraConfigs" in z_data:
                configs = z_data.get("cameraConfigs", [])
                for cfg in configs:
                    if str(cfg.get("cameraId")) == str(camera_id):
                        raw_poly = (
                            cfg.get("polygonCoordinatesJson")
                            or cfg.get("polygon_coordinates_json")
                            or cfg.get("polygon")
                            or cfg.get("points")
                        )
                        break
                if not raw_poly and len(configs) > 0:
                    raw_poly = (
                        configs[0].get("polygonCoordinatesJson")
                        or configs[0].get("polygon_coordinates_json")
                        or configs[0].get("polygon")
                        or configs[0].get("points")
                    )

            raw_poly = raw_poly or []
            enabled = bool(z_data.get("enabled", True))
            color_raw = z_data.get("color", (0, 255, 0))
            if isinstance(color_raw, list):
                color_raw = tuple(color_raw[:3])

            type_str = str(z_data.get("type", "REGION")).upper()
            z_type = ZoneType.REGION
            if "LINE" in type_str:
                z_type = ZoneType.LINE
            elif "FULL" in type_str:
                z_type = ZoneType.FULL_FRAME

            zone = PolygonLoader.load_zone(
                zone_id=z_id,
                name=z_name,
                raw_polygon=raw_poly,
                zone_type=z_type,
                enabled=enabled,
                color=color_raw,
                metadata=z_data.get("metadata", {}),
                transform_engine=transform,
            )

            self._cache.put_zone(camera_id, zone)
            loaded_zones.append(zone)

            logger.info(
                "[+] Zone: %s (ID: %s) | Vertices: %d | Area: %.1f px² | Centroid: (%d,%d) | AABB: (%d,%d)-(%d,%d)",
                zone.name,
                zone.id,
                len(zone.polygon_pixels),
                zone.area,
                zone.centroid.x,
                zone.centroid.y,
                zone.bounding_box.min_x,
                zone.bounding_box.min_y,
                zone.bounding_box.max_x,
                zone.bounding_box.max_y,
            )

        logger.info("--------------------------------------------------------------------------------")
        logger.info("[+] Spatial Cache & ZoneManager Ready (%d Zone(s) Cached for '%s')", len(loaded_zones), camera_id)
        logger.info("--------------------------------------------------------------------------------")

        return loaded_zones

    def get_zones(self, camera_id: str) -> List[ZoneModel]:
        return self._cache.get_camera_zones(camera_id)

    def get_zone_by_id(self, camera_id: str, zone_id: str) -> Optional[ZoneModel]:
        return self._cache.get_zone(camera_id, zone_id)

    def contains_point(
        self, camera_id: str, zone_id: str, point: PixelPoint | Tuple[int, int]
    ) -> bool:
        zone = self._cache.get_zone(camera_id, zone_id)
        if zone is None or not zone.enabled:
            return False

        if isinstance(point, tuple):
            point = PixelPoint(point[0], point[1])

        return zone.contains_point(point)

    def find_matching_zones(
        self, camera_id: str, point: PixelPoint | Tuple[int, int]
    ) -> List[ZoneModel]:
        if isinstance(point, tuple):
            point = PixelPoint(point[0], point[1])
        return self._cache.query_point(camera_id, point)

    def reload_camera_zones(
        self, camera_id: str, raw_zones_payload: Sequence[dict[str, Any]]
    ) -> List[ZoneModel]:
        logger.info("[+] ZoneManager: Hot-reloading spatial zones for camera '%s'...", camera_id)
        self._cache.remove_camera_zones(camera_id)
        return self.load_zones_from_backend(camera_id, raw_zones_payload)

    def clear_all(self) -> None:
        self._cache.clear()
        self._transforms.clear()
