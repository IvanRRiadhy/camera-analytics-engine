"""
Event Serializer for JSON conversion and backend schema compatibility.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from camera_analytics.events.models import BaseRuntimeEvent, SerializationLevel

logger = logging.getLogger(__name__)


class EventSerializer:
    """Serializes BaseRuntimeEvent instances into JSON payloads for AMQP and WebSocket dispatchers."""

    @staticmethod
    def serialize(
        event: Any,
        detail_level: Any = SerializationLevel.SUMMARY,
    ) -> str:
        """Serialize event to JSON string with detail_level support."""
        try:
            if hasattr(event, "to_json"):
                return event.to_json(detail_level=detail_level)
            elif hasattr(event, "to_dict"):
                return json.dumps(event.to_dict(detail_level=detail_level), ensure_ascii=False)
            return json.dumps(event, default=str, ensure_ascii=False)
        except Exception as exc:
            logger.error("[EventSerializer] Serialization failed for event: %s", exc)
            raise ValueError(f"Could not serialize event: {exc}") from exc

    @staticmethod
    def deserialize(json_str: str) -> dict[str, Any]:
        """Deserialize JSON string into dictionary payload."""
        try:
            return json.loads(json_str)
        except Exception as exc:
            logger.error("[EventSerializer] Deserialization failed: %s", exc)
            raise ValueError(f"Could not deserialize payload: {exc}") from exc
