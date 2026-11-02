"""
Envelope v1 Event Serialization Component.

Wraps vision and analytics events into the enterprise-standard Envelope v1 contract
without removing or breaking existing event fields.
"""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Union


def _format_utc_z(dt: Optional[datetime.datetime] = None) -> str:
    """Format datetime as UTC ISO 8601 with trailing 'Z'."""
    if dt is None:
        dt = datetime.datetime.now(datetime.timezone.utc)
    elif dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    else:
        dt = dt.astimezone(datetime.timezone.utc)
    iso = dt.isoformat()
    if iso.endswith("+00:00"):
        return iso[:-6] + "Z"
    if not iso.endswith("Z"):
        return iso + "Z"
    return iso


def map_category(event_type: str, plugin_name: str = "") -> str:
    """Derive category from event_type and originating plugin_name without substring matching on PERSON/HUMAN."""
    et = str(event_type).upper()
    pn = str(plugin_name).lower()

    if "VEHICLE" in et or "LPR" in et or "plate" in pn or "vehicle" in pn:
        return "vehicle"
    if et.startswith("FACE") or "FACE" in et or "DEMOGRAPHIC" in et or et == "BIOMETRIC" or "face" in pn or "biometric" in pn:
        return "biometric"
    if "ZONE" in et or "DWELL" in et or "spatial" in pn:
        return "zone"
    if "COUNT" in et or "CROSS" in et or "people" in pn:
        return "counting"
    if "ALERT" in et or "LOITER" in et or "CROWD" in et or "QUEUE" in et or "DIRECTION" in et or et in ("ENTER", "STAY", "EXIT"):
        return "behavior"
    if "ALARM" in et or "HEALTH" in et or "STATUS" in et:
        return "system"
    return "analytics"


_categorize_event = map_category


@dataclass
class EnvelopedEvent:
    """Container wrapping an event dictionary to provide object and dict protocols."""

    data: Dict[str, Any]

    @property
    def event_type(self) -> str:
        return str(self.data.get("event_type", "GENERIC_EVENT"))

    @property
    def severity(self) -> str:
        return str(self.data.get("severity", "INFO"))

    @property
    def camera_id(self) -> str:
        return str(self.data.get("camera_id", "default_camera"))

    @property
    def zone_id(self) -> Optional[str]:
        return self.data.get("zone_id")

    def to_dict(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        """Return the wrapped enveloped dictionary."""
        return self.data

    def __getattr__(self, item: str) -> Any:
        if item in self.data:
            return self.data[item]
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{item}'")

    def __getitem__(self, key: str) -> Any:
        return self.data[key]

    def __contains__(self, key: str) -> bool:
        return key in self.data

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)


class EventEnvelopeV1:
    """Envelope v1 wrapping engine."""

    def __init__(
        self,
        instance_id: Optional[str] = None,
        application_id: Optional[str] = None,
        config: Optional[Any] = None,
        mode: str = "standalone",
    ) -> None:
        self.instance_id = instance_id or "engine_edge_01"
        self._application_id = str(application_id).strip() if application_id else None
        self._config = config
        self._mode = mode

    @property
    def application_id(self) -> str:
        """Return the pre-resolved application_id."""
        return self._application_id or "00000000-0000-0000-0000-000000000000"

    @application_id.setter
    def application_id(self, val: str) -> None:
        self._application_id = val

    def wrap(self, event: Union[Any, Dict[str, Any]]) -> Dict[str, Any]:
        """Wrap an event into an Envelope v1 dictionary without removing existing fields.

        Args:
            event: BaseRuntimeEvent, StandardAnalyticsEvent, or dictionary.

        Returns:
            Enveloped dictionary containing Envelope v1 metadata and original event fields.
        """
        if hasattr(event, "to_dict"):
            base_dict = dict(event.to_dict())
        elif isinstance(event, dict):
            base_dict = dict(event)
        else:
            base_dict = {
                "raw_event": str(event),
                "event_type": getattr(event, "event_type", "GENERIC_EVENT"),
            }

        # Extract or resolve camera_id
        cam_id = (
            base_dict.get("camera_id")
            or getattr(event, "camera_id", None)
            or "c1"
        )

        # Extract or resolve zone_id (nullable)
        zone_id = (
            base_dict.get("zone_id")
            if "zone_id" in base_dict
            else getattr(event, "zone_id", None)
        )

        # Extract or derive category
        existing_cat = base_dict.get("category") or getattr(event, "category", None)
        if existing_cat:
            cat_str = str(existing_cat.value if hasattr(existing_cat, "value") else existing_cat).lower()
        else:
            evt_type = str(base_dict.get("event_type", getattr(event, "event_type", "")))
            plug_name = str(base_dict.get("plugin_name", getattr(event, "plugin_name", "")))
            cat_str = _categorize_event(evt_type, plug_name)

        # Ensure UTC timestamp with 'Z'
        ts_raw = base_dict.get("timestamp_utc") or base_dict.get("timestamp") or getattr(event, "timestamp_utc", None)
        if isinstance(ts_raw, str):
            if ts_raw.endswith("+00:00"):
                ts_utc = ts_raw[:-6] + "Z"
            elif not ts_raw.endswith("Z"):
                ts_utc = ts_raw + "Z"
            else:
                ts_utc = ts_raw
        elif isinstance(ts_raw, datetime.datetime):
            ts_utc = _format_utc_z(ts_raw)
        else:
            ts_utc = _format_utc_z()

        # Build envelope dictionary
        enveloped: Dict[str, Any] = {
            "schema_version": "1.0.0",
            "message_id": str(uuid.uuid4()),
            "category": cat_str,
            "timestamp_utc": ts_utc,
            "instance_id": self.instance_id,
            "application_id": self.application_id,
            "camera_id": str(cam_id),
            "zone_id": zone_id,
        }

        # Preserve all original fields without removing anything
        for k, v in base_dict.items():
            if k not in enveloped:
                enveloped[k] = v

        return enveloped

    def wrap_to_event(self, event: Union[Any, Dict[str, Any]]) -> EnvelopedEvent:
        """Wrap an event and return an EnvelopedEvent object wrapper."""
        return EnvelopedEvent(self.wrap(event))
