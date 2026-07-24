"""
Communication Layer Data Models & Event Serializer.

Defines the enterprise standard `StandardAnalyticsEvent` data structure and `AnalyticsEventSerializer`
for consistent JSON serialization across all network transport publishers (Log, MQTT, Kafka, etc.).
"""

from __future__ import annotations

import datetime
import json
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Optional

FRAMEWORK_VERSION = "v1.0.0"


class EventSeverity(Enum):
    """Severity classification for Analytics Events."""

    INFO = "INFO"
    WARNING = "WARNING"
    ALERT = "ALERT"
    CRITICAL = "CRITICAL"


@dataclass(slots=True)
class StandardAnalyticsEvent:
    """Enterprise Standard Analytics Event Payload.

    Transport-agnostic schema emitted by Analytics Modules to external communication publishers.

    Attributes:
        event_id: Unique UUID string identifier.
        timestamp: UTC ISO8601 formatted timestamp string.
        camera_id: Unique string camera identifier.
        camera_name: Human-readable camera name.
        analytics_module: Originating Analytics Module name.
        event_type: String identifier of event classification (e.g. 'ZONE_ENTER').
        severity: Event severity level ('INFO', 'WARNING', 'ALERT', 'CRITICAL').
        message: Human-readable event description.
        correlation_id: Optional tracking correlation ID.
        track_id: Optional associated Track ID.
        zone_id: Optional associated Zone ID.
        zone_name: Optional associated Zone name.
        frame_index: Sequential frame number.
        payload: Custom key-value dictionary payload.
        metadata: System/environment metadata dictionary.
        framework_version: Platform framework version string.
    """

    event_type: str
    message: str
    analytics_module: str = "UnknownModule"
    camera_id: str = "default_cam"
    camera_name: str = "Default Camera"
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )
    severity: str = EventSeverity.INFO.value
    correlation_id: Optional[str] = None
    track_id: Optional[int] = None
    zone_id: Optional[str] = None
    zone_name: Optional[str] = None
    frame_index: int = 0
    payload: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    framework_version: str = FRAMEWORK_VERSION

    def to_dict(self) -> dict[str, Any]:
        """Convert event payload to a clean dictionary."""
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "camera_id": self.camera_id,
            "camera_name": self.camera_name,
            "analytics_module": self.analytics_module,
            "event_type": self.event_type,
            "severity": self.severity,
            "message": self.message,
            "correlation_id": self.correlation_id,
            "track_id": self.track_id,
            "zone_id": self.zone_id,
            "zone_name": self.zone_name,
            "frame_index": self.frame_index,
            "payload": self.payload,
            "metadata": self.metadata,
            "framework_version": self.framework_version,
        }


class AnalyticsEventSerializer:
    """Thread-safe JSON Serializer for StandardAnalyticsEvent instances.

    Guarantees consistent JSON structure for all publishers.
    """

    @staticmethod
    def serialize(event: StandardAnalyticsEvent) -> str:
        """Serialize a StandardAnalyticsEvent into a JSON string formatted payload.

        Args:
            event: StandardAnalyticsEvent dataclass instance.

        Returns:
            JSON string.
        """
        return json.dumps(event.to_dict(), ensure_ascii=False)

    @staticmethod
    def deserialize(json_str: str) -> dict[str, Any]:
        """Deserialize a JSON payload back into a dictionary.

        Args:
            json_str: Valid JSON formatted string.

        Returns:
            Dictionary payload.
        """
        return json.loads(json_str)
