"""
Presentation View Models for Video Live Viewer.

Defines decoupled View Models (FramePresentation, PresentedBox, PresentedSkeleton,
PresentedTrack, PresentedZone, PresentedEvent, PresentedMetrics) separating AI domain models from UI rendering engines.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np


@dataclass(frozen=True, slots=True)
class PresentedPoint:
    """2D point coordinate for keypoints, ground points, or zone vertices."""

    x: int
    y: int
    confidence: float = 1.0


@dataclass(frozen=True, slots=True)
class PresentedBox:
    """Bounding box presentation model."""

    track_id: int
    x1: int
    y1: int
    x2: int
    y2: int
    confidence: float
    color_rgb: tuple[int, int, int] = (0, 255, 0)
    label: str = ""


@dataclass(frozen=True, slots=True)
class PresentedSkeleton:
    """17-Point COCO pose skeleton presentation model."""

    track_id: int
    keypoints: tuple[PresentedPoint, ...]
    ground_point: Optional[PresentedPoint] = None
    color_rgb: tuple[int, int, int] = (0, 255, 255)


@dataclass(frozen=True, slots=True)
class PresentedTrack:
    """Track history trajectory and state presentation model."""

    track_id: int
    state: str
    history: tuple[PresentedPoint, ...] = ()
    velocity: float = 0.0
    direction: str = "STATIONARY"


@dataclass(frozen=True, slots=True)
class PresentedZone:
    """Polygonal or Line spatial zone presentation model."""

    zone_id: str
    name: str
    zone_type: str
    points: tuple[PresentedPoint, ...]
    color_rgb: tuple[int, int, int] = (255, 0, 255)
    occupancy_count: int = 0
    status: str = "NORMAL"
    label: str = ""


@dataclass(frozen=True, slots=True)
class PresentedEvent:
    """Analytics Event alert banner presentation model."""

    event_type: str
    title: str
    message: str
    color_rgb: tuple[int, int, int] = (0, 0, 255)
    timestamp: float = 0.0


@dataclass(frozen=True, slots=True)
class PresentedMetrics:
    """Runtime HUD metrics presentation model."""

    camera_id: str
    camera_name: str
    fps_input: float
    fps_execution: float
    read_latency_ms: float
    pipeline_latency_ms: float
    gpu_id: int
    queue_size: int
    active_tracks_count: int
    active_zones_count: int


@dataclass(frozen=True, slots=True)
class FramePresentation:
    """Immutable View Model aggregating all visual elements for one frame."""

    camera_id: str
    camera_name: str
    frame_number: int
    timestamp: float
    image: np.ndarray = field(repr=False)
    boxes: tuple[PresentedBox, ...] = ()
    skeletons: tuple[PresentedSkeleton, ...] = ()
    tracks: tuple[PresentedTrack, ...] = ()
    zones: tuple[PresentedZone, ...] = ()
    events: tuple[PresentedEvent, ...] = ()
    metrics: Optional[PresentedMetrics] = None
    spatial_snapshot: Any = None
    human_view_models: tuple[Any, ...] = ()
