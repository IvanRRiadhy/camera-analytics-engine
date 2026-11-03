"""
Presentation View Models for Video Live Viewer.

Defines decoupled View Models (FramePresentation, PresentedBox, PresentedSkeleton,
PresentedTrack, PresentedZone, PresentedEvent, PresentedMetrics) separating AI domain models from UI rendering engines.
"""

from __future__ import annotations

import time
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
class PresentedFaceBox:
    """Bounding box and identification presentation model for face matching."""

    track_id: int
    x1: int
    y1: int
    x2: int
    y2: int
    label: str = ""
    person_id: str = ""
    similarity: float = 0.0
    state: str = "tracking"  # "identified" | "unknown" | "tracking"
    color_rgb: tuple[int, int, int] = (0, 255, 0)


@dataclass(frozen=True, slots=True)
class PresentedPlateBox:
    """Bounding box and text presentation model for vehicle license plates."""

    track_id: int
    x1: int
    y1: int
    x2: int
    y2: int
    plate_text: str = ""
    confidence: float = 0.0
    detector_confidence: float = 0.0
    is_consensus: bool = False
    color_rgb: tuple[int, int, int] = (0, 215, 255)
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
    plate_boxes: tuple[PresentedPlateBox, ...] = ()
    face_boxes: tuple[PresentedFaceBox, ...] = ()


@dataclass(frozen=True, slots=True)
class OverlayData:
    """Thread-safe, lightweight visual overlay view model without the raw image array."""

    camera_id: str
    camera_name: str
    frame_number: int
    timestamp: float
    boxes: tuple[PresentedBox, ...] = ()
    skeletons: tuple[PresentedSkeleton, ...] = ()
    tracks: tuple[PresentedTrack, ...] = ()
    zones: tuple[PresentedZone, ...] = ()
    events: tuple[PresentedEvent, ...] = ()
    metrics: Optional[PresentedMetrics] = None
    spatial_snapshot: Any = None
    human_view_models: tuple[Any, ...] = ()
    plate_boxes: tuple[PresentedPlateBox, ...] = ()
    face_boxes: tuple[PresentedFaceBox, ...] = ()
    created_at: float = 0.0

    @classmethod
    def from_presentation(cls, pres: FramePresentation, created_at: Optional[float] = None) -> OverlayData:
        """Create OverlayData from a FramePresentation instance, omitting the image array."""
        return cls(
            camera_id=pres.camera_id,
            camera_name=pres.camera_name,
            frame_number=pres.frame_number,
            timestamp=pres.timestamp,
            boxes=pres.boxes,
            skeletons=pres.skeletons,
            tracks=pres.tracks,
            zones=pres.zones,
            events=pres.events,
            metrics=pres.metrics,
            spatial_snapshot=pres.spatial_snapshot,
            human_view_models=pres.human_view_models,
            plate_boxes=pres.plate_boxes,
            face_boxes=pres.face_boxes,
            created_at=time.time() if created_at is None else created_at,
        )

