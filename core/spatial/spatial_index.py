"""
Spatial Index Interface and Implementations.

Defines ISpatialIndex abstraction and LinearSpatialIndex strategy for fast
containment queries and spatial filtering.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Sequence

from camera_analytics.core.spatial.models import PixelPoint, ZoneModel


class ISpatialIndex(ABC):
    """Abstract Interface for Spatial Indexing Strategies."""

    @abstractmethod
    def build(self, zones: Sequence[ZoneModel]) -> None:
        """Build or update spatial index for a sequence of ZoneModel instances."""

    @abstractmethod
    def query_point(self, point: PixelPoint) -> List[ZoneModel]:
        """Find all active zones containing query point."""

    @abstractmethod
    def clear(self) -> None:
        """Clear indexed zones."""


class LinearSpatialIndex(ISpatialIndex):
    """Fast linear scan with AABB pre-filtering ($O(N)$ for $< 50$ zones)."""

    def __init__(self) -> None:
        self._zones: list[ZoneModel] = []

    def build(self, zones: Sequence[ZoneModel]) -> None:
        self._zones = [z for z in zones if z.enabled]

    def query_point(self, point: PixelPoint) -> List[ZoneModel]:
        matching: list[ZoneModel] = []
        for zone in self._zones:
            if zone.contains_point(point):
                matching.append(zone)
        return matching

    def clear(self) -> None:
        self._zones.clear()
