"""
Spatial Geometry Subsystem Initialization.

Exposes Spatial Subsystem components cleanly:
- ZoneManager
- PolygonLoader
- RayCastingEngine
- GeometryUtils
- CoordinateTransformEngine
- SpatialVisualizer
- SpatialCache
- Models (ZoneModel, ZoneType, Point2D, PixelPoint, BoundingBox2D, Edge2D, TrackSpatialState, ZoneTransitionEvent, FrameSpatialSnapshot)
- Geometry Abstractions (IGeometry, PolygonGeometry, LineGeometry, CircleGeometry)
- Spatial Index (ISpatialIndex, LinearSpatialIndex)
- State & Transition Services (ZoneTrackerStateRepository, TransitionDetector)
"""

from __future__ import annotations

from camera_analytics.core.spatial.cache import SpatialCache
from camera_analytics.core.spatial.coordinate_transform import (
    CoordinateTransformEngine,
)
from camera_analytics.core.spatial.geometry import (
    CircleGeometry,
    IGeometry,
    LineGeometry,
    PolygonGeometry,
)
from camera_analytics.core.spatial.models import (
    BoundingBox2D,
    Edge2D,
    FrameSpatialSnapshot,
    GroundPointSource,
    PixelPoint,
    Point2D,
    PolygonOrientation,
    TrackSpatialState,
    ZoneEventType,
    ZoneModel,
    ZoneTransitionEvent,
    ZoneType,
)
from camera_analytics.core.spatial.polygon_loader import PolygonLoader
from camera_analytics.core.spatial.raycasting import (
    GeometryUtils,
    RayCastingEngine,
)
from camera_analytics.core.spatial.spatial_index import (
    ISpatialIndex,
    LinearSpatialIndex,
)
from camera_analytics.core.spatial.state_repository import (
    TrackZoneState,
    ZoneTrackerStateRepository,
)
from camera_analytics.core.spatial.transition_detector import TransitionDetector
from camera_analytics.core.spatial.visualizer import (
    OpenCVCanvasRenderer,
    RenderCommand,
    RenderPass,
    SpatialVisualizer,
)
from camera_analytics.core.spatial.zone_manager import ZoneManager

__all__ = [
    "ZoneManager",
    "PolygonLoader",
    "RayCastingEngine",
    "GeometryUtils",
    "CoordinateTransformEngine",
    "SpatialVisualizer",
    "SpatialCache",
    "ZoneModel",
    "ZoneType",
    "Point2D",
    "PixelPoint",
    "BoundingBox2D",
    "Edge2D",
    "PolygonOrientation",
    "IGeometry",
    "PolygonGeometry",
    "LineGeometry",
    "CircleGeometry",
    "ISpatialIndex",
    "LinearSpatialIndex",
    "TrackSpatialState",
    "ZoneTransitionEvent",
    "FrameSpatialSnapshot",
    "GroundPointSource",
    "ZoneEventType",
    "TrackZoneState",
    "ZoneTrackerStateRepository",
    "TransitionDetector",
    "RenderCommand",
    "RenderPass",
    "OpenCVCanvasRenderer",
]
