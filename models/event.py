"""
Event data models.

Represents analytics events produced by modules during video processing.
Events are the primary output mechanism — each analytics module emits
events when it detects meaningful situations (e.g., person entered zone,
crowd threshold exceeded, PPE violation detected).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Any, Optional


class EventSeverity(Enum):
    """Severity level of an analytics event.

    Used for filtering, prioritization, and alerting thresholds.

    Attributes:
        DEBUG: Low-level diagnostic information.
        INFO: Normal operational event (e.g., person detected).
        WARNING: Attention needed (e.g., crowd forming).
        ALERT: Immediate attention required (e.g., intrusion detected).
        CRITICAL: Highest priority (e.g., safety violation).
    """

    DEBUG = auto()
    INFO = auto()
    WARNING = auto()
    ALERT = auto()
    CRITICAL = auto()


class EventCategory(Enum):
    """Broad category grouping for analytics events.

    Allows consumers to subscribe to or filter by event category
    without knowing specific event types.

    Attributes:
        DETECTION: Object first detected.
        TRACKING: Track lifecycle changes (created, lost, deleted).
        ZONE: Zone-related events (entry, exit, dwell).
        BEHAVIOR: Behavioral analysis (loitering, running, fighting).
        COUNTING: People/vehicle counting thresholds.
        SAFETY: Safety-related events (PPE, fire, fall detection).
        SYSTEM: Framework-level events (pipeline start/stop, errors).
    """

    DETECTION = auto()
    TRACKING = auto()
    ZONE = auto()
    BEHAVIOR = auto()
    COUNTING = auto()
    SAFETY = auto()
    SYSTEM = auto()


@dataclass(frozen=True, slots=True)
class Event:
    """An analytics event emitted by a module.

    Immutable record representing something meaningful that happened
    during video analysis. Events are broadcast through the EventBus
    to all registered listeners.

    Attributes:
        event_type: Specific event type string (e.g., 'person.entered_zone').
        category: Broad category for filtering.
        severity: Severity level for prioritization.
        source_module: Name of the analytics module that emitted this event.
        timestamp: When the event occurred (UTC).
        frame_index: Video frame index when the event was detected.
        message: Human-readable description of the event.
        track_id: Optional associated track ID.
        global_id: Optional globally re-identified person ID.
        zone_id: Optional associated zone ID.
        data: Arbitrary structured data payload for event-specific details.
    """

    event_type: str
    category: EventCategory
    severity: EventSeverity
    source_module: str
    timestamp: datetime
    frame_index: int
    message: str
    track_id: Optional[int] = None
    global_id: Optional[int] = None
    zone_id: Optional[str] = None
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def is_alert(self) -> bool:
        """Whether this event is ALERT or CRITICAL severity."""
        return self.severity in (EventSeverity.ALERT, EventSeverity.CRITICAL)

    def to_dict(self) -> dict[str, Any]:
        """Serialize this event to a plain dictionary.

        Useful for JSON export, database storage, or API responses.

        Returns:
            Dictionary representation of this event.
        """
        return {
            "event_type": self.event_type,
            "category": self.category.name,
            "severity": self.severity.name,
            "source_module": self.source_module,
            "timestamp": self.timestamp.isoformat(),
            "frame_index": self.frame_index,
            "message": self.message,
            "track_id": self.track_id,
            "global_id": self.global_id,
            "zone_id": self.zone_id,
            "data": self.data,
        }


def create_event(
    event_type: str,
    category: EventCategory,
    severity: EventSeverity,
    source_module: str,
    frame_index: int,
    message: str,
    track_id: Optional[int] = None,
    global_id: Optional[int] = None,
    zone_id: Optional[str] = None,
    data: Optional[dict[str, Any]] = None,
) -> Event:
    """Factory function to create an Event with auto-generated timestamp.

    Convenience function that automatically sets the timestamp to
    the current UTC time.

    Args:
        event_type: Specific event type string.
        category: Event category.
        severity: Event severity level.
        source_module: Name of the emitting module.
        frame_index: Current video frame index.
        message: Human-readable event description.
        track_id: Optional associated track ID.
        global_id: Optional global ReID person ID.
        zone_id: Optional associated zone ID.
        data: Optional structured data payload.

    Returns:
        A new Event instance with current UTC timestamp.
    """
    return Event(
        event_type=event_type,
        category=category,
        severity=severity,
        source_module=source_module,
        timestamp=datetime.now(timezone.utc),
        frame_index=frame_index,
        message=message,
        track_id=track_id,
        global_id=global_id,
        zone_id=zone_id,
        data=data if data is not None else {},
    )
