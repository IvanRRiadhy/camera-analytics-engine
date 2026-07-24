"""
Data models package.

Exports all data models used throughout the camera analytics framework:
Detection, Track, Event, Zone, and Camera models.

Usage::

    from camera_analytics.models import Detection, Track, Event, Zone, Camera
"""

from camera_analytics.models.camera import Camera, CameraStatus
from camera_analytics.models.detection import (
    BoundingBox,
    Detection,
    DetectionClass,
    Keypoint,
    PoseKeypoints,
)
from camera_analytics.models.event import (
    Event,
    EventCategory,
    EventSeverity,
    create_event,
)
from camera_analytics.models.track import Track, TrackSnapshot, TrackState
from camera_analytics.models.zone import Point, Zone, ZoneType

__all__ = [
    # Detection
    "BoundingBox",
    "Detection",
    "DetectionClass",
    "Keypoint",
    "PoseKeypoints",
    # Track
    "Track",
    "TrackSnapshot",
    "TrackState",
    # Event
    "Event",
    "EventCategory",
    "EventSeverity",
    "create_event",
    # Zone
    "Zone",
    "ZoneType",
    "Point",
    # Camera
    "Camera",
    "CameraStatus",
]
