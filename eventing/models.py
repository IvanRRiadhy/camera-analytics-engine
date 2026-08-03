"""
Shared Platform Event Models & Schema Versioning.

Defines the immutable `PlatformEvent` contract (@dataclass(frozen=True, slots=True))
and strongly typed payload contracts for cross-runtime platform eventing.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True, slots=True)
class AnalyticsPayload:
    """Strongly typed payload for analytics events."""

    camera_id: str
    track_id: Optional[int] = None
    zone_id: Optional[str] = None
    severity: str = "INFO"
    message: str = ""
    frame_index: int = 0
    extra_data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AlarmPayload:
    """Strongly typed payload for alarm events."""

    alarm_id: str
    rule_id: str
    camera_id: str
    severity: str
    state: str
    message: str = ""


@dataclass(frozen=True, slots=True)
class IncidentPayload:
    """Strongly typed payload for incident events."""

    incident_id: str
    title: str
    camera_id: str
    severity: str
    alarm_count: int = 0


@dataclass(frozen=True, slots=True)
class PlatformEvent:
    """Immutable Platform Event Contract (@dataclass(frozen=True, slots=True)).

    Attributes:
        event_id: Unique UUID v4 event identifier.
        event_type: String classification (e.g. 'ANALYTICS_EVENT', 'ALARM_CREATED').
        version: Semantic schema version string (e.g. '1.0').
        source: Originating component or plugin name.
        timestamp: Epoch timestamp in UTC seconds.
        payload: Strongly typed event payload object.
    """

    event_id: str
    event_type: str
    version: str = "1.0"
    source: str = "platform"
    timestamp: float = field(default_factory=time.time)
    payload: Any = None

    @classmethod
    def create(
        cls,
        event_type: str,
        payload: Any,
        source: str = "platform",
        version: str = "1.0",
    ) -> PlatformEvent:
        """Construct a new immutable PlatformEvent."""
        return cls(
            event_id=f"pe_{uuid.uuid4().hex[:8]}",
            event_type=event_type,
            version=version,
            source=source,
            timestamp=time.time(),
            payload=payload,
        )


class EventSchemaVersion:
    """Semantic versioning validator for PlatformEvent contracts."""

    SUPPORTED_VERSIONS = {"1.0", "1.1", "2.0"}

    @classmethod
    def is_compatible(cls, version: str) -> bool:
        """Check if event schema version is supported by current runtime."""
        return version.strip() in cls.SUPPORTED_VERSIONS
