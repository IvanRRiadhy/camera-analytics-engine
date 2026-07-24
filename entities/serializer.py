"""
Entity Serializer Package.

Transforms strongly typed Domain Entities (TrackEntity, CameraEntity, FrameEntity, ZoneEntity)
and AnalyticsPayload instances into StandardAnalyticsEvent payloads and clean JSON dictionaries.
Modul Analytics does not construct manual JSON strings.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from camera_analytics.communication.models import StandardAnalyticsEvent
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
    ) -> StandardAnalyticsEvent:
        """Construct a standardized StandardAnalyticsEvent payload from Domain Entities.

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

        camera_id = camera.camera_id if camera else "default_cam"
        camera_name = camera.camera_name if camera else "Default Camera"
        frame_idx = frame.frame_index if frame else 0
        tr_id = track.track_id if track else None
        z_id = zone.zone_id if zone else None
        z_name = zone.zone_name if zone else None

        return StandardAnalyticsEvent(
            event_type=event_type,
            message=message,
            analytics_module=analytics_module,
            camera_id=camera_id,
            camera_name=camera_name,
            severity=severity,
            track_id=tr_id,
            zone_id=z_id,
            zone_name=z_name,
            frame_index=frame_idx,
            payload=payload_dict,
            metadata={
                "frame": frame.to_dict() if frame else None,
                "camera": camera.to_dict() if camera else None,
            },
        )

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
