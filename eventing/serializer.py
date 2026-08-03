"""
Platform Event Serializer Implementation.

Serializes immutable `PlatformEvent` instances to JSON text and deserializes JSON to dataclasses.
"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from typing import Any

from camera_analytics.eventing.models import PlatformEvent


class PlatformEventSerializer:
    """JSON Serializer for PlatformEvent objects."""

    @staticmethod
    def to_dict(event: PlatformEvent) -> dict[str, Any]:
        """Convert PlatformEvent to dictionary."""
        payload_data = asdict(event.payload) if is_dataclass(event.payload) else event.payload
        return {
            "event_id": event.event_id,
            "event_type": event.event_type,
            "version": event.version,
            "source": event.source,
            "timestamp": round(event.timestamp, 3),
            "payload": payload_data,
        }

    @classmethod
    def to_json(cls, event: PlatformEvent) -> str:
        """Serialize PlatformEvent to JSON string."""
        return json.dumps(cls.to_dict(event), indent=None, separators=(",", ":"))
