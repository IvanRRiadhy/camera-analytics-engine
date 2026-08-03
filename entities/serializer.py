"""
Entity Serializer Package.

Transforms strongly typed Domain Entities (TrackEntity, CameraEntity, FrameEntity, ZoneEntity)
and AnalyticsPayload instances into StandardAnalyticsEvent payloads and clean JSON dictionaries.
Modul Analytics does not construct manual JSON strings.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from camera_analytics.communication.models import EventSeverity, StandardAnalyticsEvent
from camera_analytics.entities.models import (
    CameraEntity,
    FrameEntity,
    TrackEntity,
    ZoneEntity,
)
from camera_analytics.entities.payload import AnalyticsPayload


class EntitySerializer:
    """Serializer responsible for converting Domain Entities & AnalyticsPayload objects to AnalyticsEvents and JSON."""

    @classmethod
    def serialize_payload(cls, payload: AnalyticsPayload | dict[str, Any]) -> dict[str, Any]:
        """Convert AnalyticsPayload instance or dictionary to clean payload dict.

        Args:
            payload: AnalyticsPayload instance or raw dict.

        Returns:
            Dictionary payload.
        """
        if isinstance(payload, AnalyticsPayload):
            return payload.to_dict()
        return dict(payload)

    @classmethod
    def build_analytics_event(
        cls,
        event_type: str,
        message: str,
        analytics_module: str,
        camera: Optional[CameraEntity] = None,
        frame: Optional[FrameEntity] = None,
        track: Optional[TrackEntity] = None,
        zone: Optional[ZoneEntity] = None,
        payload: Optional[AnalyticsPayload | dict[str, Any]] = None,
        severity: str = "INFO",
        correlation_id: Optional[str] = None,
        track_id: Optional[int] = None,
        zone_id: Optional[str] = None,
        zone_name: Optional[str] = None,
    ) -> StandardAnalyticsEvent:
        """Construct a standardized StandardAnalyticsEvent payload from Domain Entities and raw data.

        Args:
            event_type: String identifier of event classification (e.g. 'ZONE_ENTER').
            message: Human-readable message.
            analytics_module: Originating module string name.
            camera: Optional CameraEntity instance.
            frame: Optional FrameEntity instance.
            track: Optional TrackEntity instance.
            zone: Optional ZoneEntity instance.
            payload: Optional AnalyticsPayload or dict payload.
            severity: Event severity ('INFO', 'WARNING', 'ALERT', 'CRITICAL').
            correlation_id: Optional correlation ID string.
            track_id: Explicit track ID integer fallback.
            zone_id: Explicit zone ID string fallback.
            zone_name: Explicit zone name string fallback.

        Returns:
            StandardAnalyticsEvent instance ready for Communication Layer enqueueing.
        """
        payload_dict = cls.serialize_payload(payload) if payload is not None else {}

        # Merge track entity summary into payload if provided
        if track is not None and "track" not in payload_dict:
            payload_dict["track"] = track.to_dict()

        # Merge zone entity summary into payload if provided
        if zone is not None and "zone" not in payload_dict:
            payload_dict["zone"] = zone.to_dict()

        # Derive camera info
        camera_id = camera.camera_id if camera else payload_dict.get("camera_id", "default_cam")
        camera_name = camera.camera_name if camera else payload_dict.get("camera_name", "Default Camera")

        # Derive frame info
        frame_idx = frame.frame_index if frame else payload_dict.get("frame_index", 0)

        # Derive track ID
        derived_track_id = track.track_id if track else (track_id if track_id is not None else payload_dict.get("track_id"))

        # Derive zone ID and zone name
        derived_zone_id = zone.zone_id if zone else (zone_id if zone_id else payload_dict.get("zone_id"))
        derived_zone_name = zone.zone_name if zone else (zone_name if zone_name else payload_dict.get("zone_name"))

        # Fallback zone_name to zone_id if zone_name is None
        if derived_zone_id and not derived_zone_name:
            derived_zone_name = str(derived_zone_id)

        # Derive correlation ID if in payload
        derived_corr_id = correlation_id or payload_dict.get("correlation_id")

        metadata_dict: dict[str, Any] = {
            "camera": camera.to_dict() if camera else {"camera_id": camera_id, "camera_name": camera_name},
            "frame": frame.to_dict() if frame else {"frame_index": frame_idx},
        }

        # Build StandardAnalyticsEvent
        event_kwargs: dict[str, Any] = {
            "event_type": event_type,
            "message": message,
            "analytics_module": analytics_module,
            "camera_id": camera_id,
            "camera_name": camera_name,
            "severity": severity,
            "track_id": derived_track_id,
            "zone_id": derived_zone_id,
            "zone_name": derived_zone_name,
            "frame_index": frame_idx,
            "payload": payload_dict,
            "metadata": metadata_dict,
        }
        if derived_corr_id:
            event_kwargs["correlation_id"] = derived_corr_id

        return StandardAnalyticsEvent(**event_kwargs)

    @classmethod
    def to_json(cls, entity: Any) -> str:
        """Serialize any Entity or AnalyticsPayload object into a JSON string.

        Args:
            entity: Domain Entity instance or AnalyticsPayload instance.

        Returns:
            Formatted JSON string.
        """
        if hasattr(entity, "to_dict"):
            data = entity.to_dict()
        else:
            data = str(entity)

        return json.dumps(data, ensure_ascii=False)
