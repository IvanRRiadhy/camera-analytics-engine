"""
Coordinate Transformation Engine.

Converts normalized coordinates [0.0, 1.0] to pixel coordinates [0, width/height]
and vice versa. Performs caching to avoid recomputation on identical frame resolutions.
"""

from __future__ import annotations

import logging
from typing import Sequence, Tuple

from camera_analytics.core.spatial.models import PixelPoint, Point2D

logger = logging.getLogger(__name__)


class CoordinateTransformEngine:
    """High-performance Coordinate Space Transformation Engine."""

    def __init__(self, frame_width: int = 1920, frame_height: int = 1080) -> None:
        self._frame_width = max(1, frame_width)
        self._frame_height = max(1, frame_height)

    @property
    def resolution(self) -> Tuple[int, int]:
        """Current frame resolution (width, height)."""
        return (self._frame_width, self._frame_height)

    def set_resolution(self, frame_width: int, frame_height: int) -> bool:
        """Update resolution. Returns True if resolution changed."""
        new_w = max(1, frame_width)
        new_h = max(1, frame_height)
        if new_w != self._frame_width or new_h != self._frame_height:
            logger.info(
                "[+] CoordinateTransformEngine: Resolution updated from %dx%d to %dx%d",
                self._frame_width,
                self._frame_height,
                new_w,
                new_h,
            )
            self._frame_width = new_w
            self._frame_height = new_h
            return True
        return False

    def normalized_to_pixel_point(self, point: Point2D) -> PixelPoint:
        """Convert a single normalized Point2D (0.0 - 1.0) to a PixelPoint."""
        px = int(round(point.x * self._frame_width))
        py = int(round(point.y * self._frame_height))
        # Clamp within frame bounds
        px = max(0, min(self._frame_width - 1, px))
        py = max(0, min(self._frame_height - 1, py))
        return PixelPoint(x=px, y=py)

    def normalized_to_pixel_polygon(
        self, normalized_points: Sequence[Point2D]
    ) -> list[PixelPoint]:
        """Convert a list of normalized Point2D coordinates to PixelPoint coordinates."""
        return [self.normalized_to_pixel_point(pt) for pt in normalized_points]

    def pixel_to_normalized_point(self, point: PixelPoint) -> Point2D:
        """Convert a PixelPoint to normalized float Point2D [0.0 - 1.0]."""
        nx = max(0.0, min(1.0, point.x / float(self._frame_width)))
        ny = max(0.0, min(1.0, point.y / float(self._frame_height)))
        return Point2D(x=nx, y=ny)
