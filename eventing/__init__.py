"""
Standalone Enterprise Platform Event Infrastructure Package.

Provides the unified `PlatformEvent` contract, pub-sub `PlatformEventBus`, `PlatformEventRouter`,
`PlatformEventSerializer`, and `EventSchemaVersion` validator shared across all platform runtimes.
"""

from camera_analytics.eventing.event_bus import PlatformEventBus
from camera_analytics.eventing.models import (
    AlarmPayload,
    AnalyticsPayload,
    EventSchemaVersion,
    IncidentPayload,
    PlatformEvent,
)
from camera_analytics.eventing.router import PlatformEventRouter
from camera_analytics.eventing.serializer import PlatformEventSerializer

__all__ = [
    "PlatformEvent",
    "AnalyticsPayload",
    "AlarmPayload",
    "IncidentPayload",
    "EventSchemaVersion",
    "PlatformEventBus",
    "PlatformEventRouter",
    "PlatformEventSerializer",
]
