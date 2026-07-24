"""
Domain Entity Model & Payload SDK Package.

Provides strongly typed Entity representations, Payload SDK builders, Entity Factory,
and Entity Serializer for enterprise video analytics modules.
"""

from camera_analytics.entities.factory import EntityFactory
from camera_analytics.entities.models import (
    BoundingBoxEntity,
    CameraEntity,
    DirectionEntity,
    FrameEntity,
    GroundPointEntity,
    GroundPointSource,
    KeypointEntity,
    PoseEntity,
    TrackEntity,
    VelocityEntity,
    ZoneEntity,
    ZoneState,
)
from camera_analytics.entities.payload import (
    AnalyticsPayload,
    BehaviorPayload,
    CrowdPayload,
    DwellTimePayload,
    HeatmapPayload,
    LineCrossingPayload,
    LoiteringPayload,
    PeoplePayload,
    PPEPayload,
    ReIDPayload,
)
from camera_analytics.entities.serializer import EntitySerializer

__all__ = [
    "BoundingBoxEntity",
    "GroundPointEntity",
    "GroundPointSource",
    "VelocityEntity",
    "DirectionEntity",
    "KeypointEntity",
    "PoseEntity",
    "ZoneEntity",
    "ZoneState",
    "TrackEntity",
    "FrameEntity",
    "CameraEntity",
    "PeoplePayload",
    "PPEPayload",
    "CrowdPayload",
    "LineCrossingPayload",
    "LoiteringPayload",
    "DwellTimePayload",
    "BehaviorPayload",
    "ReIDPayload",
    "HeatmapPayload",
    "AnalyticsPayload",
    "EntityFactory",
    "EntitySerializer",
]
