"""
Unified Runtime Event Model Contracts for camera_analytics platform.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class SerializationLevel(Enum):
    """Logging & transport detail level classification."""

    SUMMARY = "summary"
    STANDARD = "standard"
    RUNTIME = "runtime"
    FULL = "full"


@dataclass
class BaseRuntimeEvent:
    """Base Event Contract for all vision analytics runtime events.

    Attributes:
        event_id: Unique UUID identifier.
        timestamp_utc: ISO8601 timestamp string.
        engine_instance_id: Edge AI Engine Instance ID.
        worker_node_id: Worker Node ID.
        pipeline_assignment_id: Camera Pipeline Assignment ID.
        camera_id: Target Camera ID.
        analytics_module_id: Analytics Module ID.
        plugin_name: Originating vision plugin name.
        event_type: String classification identifier.
        severity: Event severity level ('INFO', 'WARNING', 'CRITICAL').
        confidence: Inference detection confidence score (0.0 to 1.0).
        track_id: Optional object track ID.
        zone_id: Optional spatial zone ID.
        bounding_box: Normalized [x1, y1, x2, y2] bounding box.
        polygon: Spatial zone polygon coordinates.
        snapshot_path: Optional file path to captured frame snapshot.
        attributes: Custom plugin-specific attributes dictionary.
        metadata: System metadata dictionary.
    """

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    engine_instance_id: str = "engine_edge_01"
    worker_node_id: Optional[str] = None
    pipeline_assignment_id: str = "pipeline_default"
    camera_id: str = "c1"
    analytics_module_id: Optional[str] = None
    plugin_name: str = "BasePlugin"
    event_type: str = "BASE_EVENT"
    severity: str = "INFO"
    confidence: float = 0.95
    track_id: Optional[int] = None
    zone_id: Optional[str] = None
    bounding_box: Optional[list[float]] = None
    polygon: Optional[list[list[float]]] = None
    snapshot_path: Optional[str] = None
    attributes: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(
        self,
        detail_level: Optional[SerializationLevel | str] = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Convert event instance to dictionary with optional detail_level support."""
        level = detail_level
        if isinstance(level, str):
            try:
                level = SerializationLevel(level.lower())
            except ValueError:
                level = SerializationLevel.STANDARD

        res = {
            "event_id": self.event_id,
            "timestamp_utc": self.timestamp_utc,
            "engine_instance_id": self.engine_instance_id,
            "worker_node_id": self.worker_node_id,
            "pipeline_assignment_id": self.pipeline_assignment_id,
            "camera_id": self.camera_id,
            "analytics_module_id": self.analytics_module_id,
            "plugin_name": self.plugin_name,
            "event_type": self.event_type,
            "severity": self.severity,
            "confidence": self.confidence,
            "track_id": self.track_id,
            "zone_id": self.zone_id,
            "bounding_box": self.bounding_box,
            "polygon": self.polygon,
            "snapshot_path": self.snapshot_path,
            "attributes": self.attributes,
            "metadata": self.metadata,
        }

        if level == SerializationLevel.SUMMARY:
            res.pop("metadata", None)
            res.pop("worker_node_id", None)
            res.pop("analytics_module_id", None)

        return res

    def to_json(
        self,
        detail_level: Optional[SerializationLevel | str] = None,
        **kwargs: Any,
    ) -> str:
        """Serialize event instance to compact JSON string."""
        return json.dumps(self.to_dict(detail_level=detail_level, **kwargs), ensure_ascii=False)


@dataclass
class DetectionEvent(BaseRuntimeEvent):
    """Specialized event for general object detection."""

    event_type: str = "DETECTION"
    object_class: str = "person"


@dataclass
class TrackingEvent(BaseRuntimeEvent):
    """Specialized event for object trajectory tracking."""

    event_type: str = "TRACKING"
    dwell_time_seconds: float = 0.0


@dataclass
class CountingEvent(BaseRuntimeEvent):
    """Specialized event for bidirectional line-crossing and people counting."""

    event_type: str = "COUNTING"
    count_in: int = 0
    count_out: int = 0
    current_occupancy: int = 0


@dataclass
class AlertEvent(BaseRuntimeEvent):
    """Specialized event for security and operational alerts."""

    event_type: str = "ALERT"
    severity: str = "WARNING"
    alert_rule_code: str = "ZONE_INTRUSION"
    message: str = "Alert triggered"


@dataclass
class HealthEvent(BaseRuntimeEvent):
    """Specialized event for node and plugin health updates."""

    event_type: str = "HEALTH"
    status: str = "OK"


@dataclass
class VehicleEvent(BaseRuntimeEvent):
    """Specialized event for vehicle classification and traffic mobility."""

    event_type: str = "VEHICLE"
    vehicle_type: str = "car"
    license_plate: Optional[str] = None


@dataclass
class FaceRecognitionEvent(BaseRuntimeEvent):
    """Specialized event for biometric face recognition."""

    event_type: str = "FACE_RECOGNITION"
    person_name: Optional[str] = None
    watchlist_id: Optional[str] = None


@dataclass
class PPEEvent(BaseRuntimeEvent):
    """Specialized event for safety gear compliance monitoring."""

    event_type: str = "PPE"
    hardhat_detected: bool = True
    vest_detected: bool = True
    is_compliant: bool = True


@dataclass
class FireEvent(BaseRuntimeEvent):
    """Specialized event for optical fire and smoke detection."""

    event_type: str = "FIRE_SMOKE"
    severity: str = "CRITICAL"
    hazard_type: str = "SMOKE"
