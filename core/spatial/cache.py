"""
Spatial Geometry Cache consuming ISpatialIndex.

Thread-safe storage of precomputed ZoneModel objects indexed by camera_id
and accelerated via ISpatialIndex interface strategies.
"""

from __future__ import annotations

import logging
import threading
from typing import Dict, List, Optional

from camera_analytics.core.spatial.models import PixelPoint, ZoneModel
from camera_analytics.core.spatial.spatial_index import ISpatialIndex, LinearSpatialIndex

logger = logging.getLogger(__name__)


class SpatialCache:
    """Thread-safe In-Memory Cache for Precomputed Spatial Zones with ISpatialIndex acceleration."""

    def __init__(self, index_factory: Optional[type[ISpatialIndex]] = None) -> None:
        self._lock = threading.RLock()
        self._zones: Dict[str, Dict[str, ZoneModel]] = {}
        self._indexes: Dict[str, ISpatialIndex] = {}
        self._index_factory = index_factory or LinearSpatialIndex

    def put_zone(self, camera_id: str, zone: ZoneModel) -> None:
        with self._lock:
            if camera_id not in self._zones:
                self._zones[camera_id] = {}
                self._indexes[camera_id] = self._index_factory()

            self._zones[camera_id][zone.id] = zone
            self._indexes[camera_id].build(list(self._zones[camera_id].values()))
            logger.debug("[+] SpatialCache: Cached zone '%s' for camera '%s'", zone.id, camera_id)

    def get_zone(self, camera_id: str, zone_id: str) -> Optional[ZoneModel]:
        with self._lock:
            return self._zones.get(camera_id, {}).get(zone_id)

    def get_camera_zones(self, camera_id: str) -> List[ZoneModel]:
        with self._lock:
            cam_dict = self._zones.get(camera_id, {})
            return [z for z in cam_dict.values() if z.enabled]

    def query_point(self, camera_id: str, point: PixelPoint) -> List[ZoneModel]:
        with self._lock:
            idx = self._indexes.get(camera_id)
            if idx is None:
                return []
            return idx.query_point(point)

    def remove_camera_zones(self, camera_id: str) -> bool:
        with self._lock:
            if camera_id in self._zones:
                del self._zones[camera_id]
                if camera_id in self._indexes:
                    del self._indexes[camera_id]
                logger.info("[+] SpatialCache: Cleared cached zones for camera '%s'", camera_id)
                return True
            return False

    def clear(self) -> None:
        with self._lock:
            self._zones.clear()
            self._indexes.clear()
            logger.info("[+] SpatialCache: In-memory spatial cache cleared.")
