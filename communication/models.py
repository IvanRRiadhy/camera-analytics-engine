"""
Communication Layer Data Models & Event Serializer.

Defines the enterprise standard `StandardAnalyticsEvent` data structure, `EventDetailLevel` enum,
and `AnalyticsEventSerializer` for consistent JSON serialization across all network transport publishers.
"""

from __future__ import annotations

import datetime
import json
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

FRAMEWORK_VERSION = "v1.0.0"
SCHEMA_VERSION = "1.0"


class EventSeverity(Enum):
    """Severity classification for Analytics Events."""

    INFO = "INFO"
    WARNING = "WARNING"
    ALERT = "ALERT"
    CRITICAL = "CRITICAL"


class EventDetailLevel(Enum):
    """Logging detail level classification for event payload serialization."""

    SUMMARY = "summary"      # Production default: 300-700 bytes (Business Event)
    STANDARD = "standard"    # Production debugging: 700-1200 bytes
    FULL = "full"            # Dev & AI diagnostics: 2000-3500 bytes (Telemetry)


@dataclass(slots=True)
class StandardAnalyticsEvent:
    """Enterprise Standard Analytics Event Payload.

    Transport-agnostic schema emitted by Analytics Modules to external communication publishers.

    Attributes:
        event_id: Unique UUID v4 string identifier.
        schema_version: Event schema version string (default "1.0").
        event_type: String identifier of event classification (e.g. 'ZONE_ENTER').
        analytics_module: Originating Analytics Module name.
        source_module: Alias for analytics_module for backwards compatibility.
        severity: Event severity level ('INFO', 'WARNING', 'ALERT', 'CRITICAL').
        message: Human-readable event description.
        timestamp: UTC ISO8601 formatted timestamp string.
        correlation_id: Unique string UUID for distributed tracing.
        camera_id: Unique string camera identifier.
        camera_name: Human-readable camera name.
        track_id: Optional associated Track ID.
        zone_id: Optional associated Zone ID.
        zone_name: Optional associated Zone name.
        frame_index: Sequential frame number.
        payload: Custom key-value dictionary payload.
        metadata: System/environment metadata dictionary.
        framework_version: Platform framework version string.
    """

    event_type: str = "GENERIC_EVENT"
    message: str = ""
    analytics_module: str = "UnknownModule"
    source_module: Optional[str] = None
    camera_id: str = "default_cam"
    camera_name: str = "Default Camera"
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    schema_version: str = SCHEMA_VERSION
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )
    severity: str = EventSeverity.INFO.value
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    track_id: Optional[int] = None
    zone_id: Optional[str] = None
    zone_name: Optional[str] = None
    frame_index: int = 0
    payload: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    framework_version: str = FRAMEWORK_VERSION

    def __post_init__(self) -> None:
        """Synchronize analytics_module and source_module fields."""
        if hasattr(self.severity, "value"):
            object.__setattr__(self, "severity", self.severity.value)
        if self.source_module and (not self.analytics_module or self.analytics_module == "UnknownModule"):
            object.__setattr__(self, "analytics_module", self.source_module)
        elif self.analytics_module and not self.source_module:
            object.__setattr__(self, "source_module", self.analytics_module)

    def _build_optimized_payload(self, detail_level: EventDetailLevel) -> dict[str, Any]:
        """Compact payload dictionary based on requested detail level."""
        if not isinstance(self.payload, dict):
            return self.payload

        p = dict(self.payload)

        # Strip redundant duplicated fields inside payload
        p.pop("camera_id", None)
        p.pop("timestamp", None)

        # Handle track dict optimization if present inside payload
        if "track" in p and isinstance(p["track"], dict):
            tr = dict(p["track"])

            # Strip pose in SUMMARY and STANDARD modes
            if detail_level != EventDetailLevel.FULL:
                tr.pop("pose", None)

            # Compact bbox dictionary to [x1, y1, x2, y2] list
            if "bbox" in tr and isinstance(tr["bbox"], dict):
                b = tr["bbox"]
                if "x1" in b and "y1" in b and "x2" in b and "y2" in b:
                    tr["bbox"] = [b["x1"], b["y1"], b["x2"], b["y2"]]

            # Compact ground point to [x, y] list
            if "ground_point" in tr and isinstance(tr["ground_point"], dict):
                gp = tr["ground_point"]
                if "x" in gp and "y" in gp:
                    tr["ground_point"] = [gp["x"], gp["y"]]

            # In SUMMARY mode, retain only essential track fields
            if detail_level == EventDetailLevel.SUMMARY:
                tr.pop("feature_store", None)
                tr.pop("velocity", None)
                tr.pop("direction", None)

            p["track"] = tr

        # Compact top-level bbox in payload if present as dict
        if "bbox" in p and isinstance(p["bbox"], dict):
            b = p["bbox"]
            if "x1" in b and "y1" in b and "x2" in b and "y2" in b:
                p["bbox"] = [b["x1"], b["y1"], b["x2"], b["y2"]]

        # Compact ground point in payload if present as dict
        if "ground_point" in p and isinstance(p["ground_point"], dict):
            gp = p["ground_point"]
            if "x" in gp and "y" in gp:
                p["ground_point"] = [gp["x"], gp["y"]]

        return p

    def to_dict(self, detail_level: Optional[EventDetailLevel | str] = None) -> dict[str, Any]:
        """Convert event payload to clean dictionary optimized for the requested detail level."""
        mod_name = self.analytics_module or self.source_module or "UnknownModule"

        if detail_level is None:
            # Default to full canonical representation for backward compatibility
            return {
                "event_id": self.event_id,
                "schema_version": self.schema_version,
                "event_type": self.event_type,
                "analytics_module": mod_name,
                "source_module": mod_name,
                "severity": self.severity,
                "message": self.message,
                "timestamp": self.timestamp,
                "correlation_id": self.correlation_id,
                "camera_id": self.camera_id,
                "camera_name": self.camera_name,
                "track_id": self.track_id,
                "zone_id": self.zone_id,
                "zone_name": self.zone_name,
                "frame_index": self.frame_index,
                "payload": self.payload,
                "metadata": self.metadata,
                "framework_version": self.framework_version,
            }

        if isinstance(detail_level, str):
            try:
                detail_level = EventDetailLevel(detail_level.lower())
            except ValueError:
                detail_level = EventDetailLevel.SUMMARY

        clean_payload = self._build_optimized_payload(detail_level)

        if detail_level == EventDetailLevel.SUMMARY:
            # Compact Business Event: Exclude nested heavy camera/frame/pose objects
            res = {
                "event_id": self.event_id,
                "schema_version": self.schema_version,
                "event_type": self.event_type,
                "analytics_module": mod_name,
                "severity": self.severity,
                "timestamp": self.timestamp,
                "correlation_id": self.correlation_id,
                "camera_id": self.camera_id,
                "frame_index": self.frame_index,
                "payload": clean_payload,
            }
            if self.track_id is not None:
                res["track_id"] = self.track_id
            if self.zone_id is not None:
                res["zone_id"] = self.zone_id
            if self.zone_name is not None:
                res["zone_name"] = self.zone_name
            return res

        elif detail_level == EventDetailLevel.STANDARD:
            # Production Debugging Mode
            res = {
                "event_id": self.event_id,
                "schema_version": self.schema_version,
                "event_type": self.event_type,
                "analytics_module": mod_name,
                "severity": self.severity,
                "message": self.message,
                "timestamp": self.timestamp,
                "correlation_id": self.correlation_id,
                "camera_id": self.camera_id,
                "camera_name": self.camera_name,
                "track_id": self.track_id,
                "zone_id": self.zone_id,
                "zone_name": self.zone_name,
                "frame_index": self.frame_index,
                "payload": clean_payload,
            }
            return res

        else:
            # FULL mode (Development / Diagnostics)
            return {
                "event_id": self.event_id,
                "schema_version": self.schema_version,
                "event_type": self.event_type,
                "analytics_module": mod_name,
                "source_module": mod_name,
                "severity": self.severity,
                "message": self.message,
                "timestamp": self.timestamp,
                "correlation_id": self.correlation_id,
                "camera_id": self.camera_id,
                "camera_name": self.camera_name,
                "track_id": self.track_id,
                "zone_id": self.zone_id,
                "zone_name": self.zone_name,
                "frame_index": self.frame_index,
                "payload": clean_payload,
                "metadata": self.metadata,
                "framework_version": self.framework_version,
            }


def _json_default(o: Any) -> Any:
    """Fallback serializer for non-standard JSON types (numpy scalars, ndarrays, Path, dates)."""
    try:
        import numpy as np
        if isinstance(o, np.generic):
            return o.item()
        if isinstance(o, np.ndarray):
            return o.tolist()
    except ImportError:
        pass

    import pathlib
    if isinstance(o, pathlib.Path):
        return str(o)

    if isinstance(o, (datetime.datetime, datetime.date)):
        return o.isoformat()

    if isinstance(o, (set, tuple)):
        return list(o)

    raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")


class AnalyticsEventSerializer:
    """Thread-safe JSON Serializer for StandardAnalyticsEvent instances.

    Guarantees strict single-line NDJSON format with UTF-8 encoding.
    """

    @staticmethod
    def serialize(
        event: StandardAnalyticsEvent,
        detail_level: EventDetailLevel | str = EventDetailLevel.SUMMARY,
    ) -> str:
        """Serialize a StandardAnalyticsEvent into a single-line compact JSON string payload.

        Args:
            event: StandardAnalyticsEvent dataclass instance.
            detail_level: Desired detail level ('summary', 'standard', 'full').

        Returns:
            Single-line JSON string without raw newlines.
        """
        return json.dumps(
            event.to_dict(detail_level=detail_level),
            ensure_ascii=False,
            separators=(",", ":"),
            default=_json_default,
        )

    @staticmethod
    def deserialize(json_str: str) -> dict[str, Any]:
        """Deserialize a JSON payload string back into a dictionary.

        Args:
            json_str: Valid JSON formatted string.

        Returns:
            Dictionary payload.
        """
        return json.loads(json_str)
