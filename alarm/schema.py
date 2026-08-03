"""
Enterprise Alarm & Incident Management Schemas.

Defines strongly typed data structures for Alarms, Incidents, AlarmRules,
EscalationPolicies, OperatorActions, Notifications, and Evidence Packages.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class AlarmState(str, Enum):
    """Alarm Lifecycle States."""

    NEW = "NEW"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    INVESTIGATING = "INVESTIGATING"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class AlarmSeverity(str, Enum):
    """Alarm Severity Levels."""

    INFO = "INFO"
    WARNING = "WARNING"
    ALERT = "ALERT"
    CRITICAL = "CRITICAL"


@dataclass(slots=True)
class OperatorAction:
    """Audit log entry for operator state transitions or notes."""

    action_id: str
    alarm_id: str
    operator_id: str
    action_type: str  # e.g., 'ACKNOWLEDGE', 'INVESTIGATE', 'RESOLVE', 'COMMENT'
    timestamp: float
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "alarm_id": self.alarm_id,
            "operator_id": self.operator_id,
            "action_type": self.action_type,
            "timestamp": round(self.timestamp, 3),
            "note": self.note,
        }


@dataclass(slots=True)
class Alarm:
    """Actionable Enterprise Alarm generated from StandardAnalyticsEvents."""

    alarm_id: str
    rule_id: str
    rule_name: str
    event_id: str
    event_type: str
    camera_id: str
    zone_id: Optional[str]
    severity: AlarmSeverity
    state: AlarmState = AlarmState.NEW
    created_at: float = field(default_factory=time.time)
    acknowledged_at: Optional[float] = None
    resolved_at: Optional[float] = None
    closed_at: Optional[float] = None
    assigned_operator: Optional[str] = None
    track_id: Optional[int] = None
    snapshot_path: Optional[str] = None
    message: str = ""
    history: list[OperatorAction] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "alarm_id": self.alarm_id,
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "event_id": self.event_id,
            "event_type": self.event_type,
            "camera_id": self.camera_id,
            "zone_id": self.zone_id,
            "severity": self.severity.value,
            "state": self.state.value,
            "created_at": round(self.created_at, 3),
            "acknowledged_at": round(self.acknowledged_at, 3) if self.acknowledged_at else None,
            "resolved_at": round(self.resolved_at, 3) if self.resolved_at else None,
            "closed_at": round(self.closed_at, 3) if self.closed_at else None,
            "assigned_operator": self.assigned_operator,
            "track_id": self.track_id,
            "snapshot_path": self.snapshot_path,
            "message": self.message,
            "history": [h.to_dict() for h in self.history],
        }


@dataclass(slots=True)
class Incident:
    """Grouped correlation case containing multiple related alarms and events."""

    incident_id: str
    title: str
    camera_id: str
    zone_id: Optional[str]
    severity: AlarmSeverity
    state: AlarmState = AlarmState.NEW
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    alarm_ids: list[str] = field(default_factory=list)
    event_ids: list[str] = field(default_factory=list)
    assigned_operator: Optional[str] = None
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "title": self.title,
            "camera_id": self.camera_id,
            "zone_id": self.zone_id,
            "severity": self.severity.value,
            "state": self.state.value,
            "created_at": round(self.created_at, 3),
            "updated_at": round(self.updated_at, 3),
            "alarm_ids": self.alarm_ids,
            "event_ids": self.event_ids,
            "assigned_operator": self.assigned_operator,
            "summary": self.summary,
        }


@dataclass(slots=True)
class AlarmRule:
    """Declarative configuration rule for triggering alarms from events."""

    rule_id: str
    name: str
    enabled: bool = True
    event_types: list[str] = field(default_factory=list)
    severities: list[str] = field(default_factory=list)
    cameras: list[str] = field(default_factory=list)
    zones: list[str] = field(default_factory=list)
    min_confidence: float = 0.0
    min_occupancy: int = 0
    min_dwell_sec: float = 0.0
    debounce_sec: float = 0.0
    suppression_sec: float = 0.0
    target_severity: Optional[AlarmSeverity] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "enabled": self.enabled,
            "event_types": self.event_types,
            "severities": self.severities,
            "cameras": self.cameras,
            "zones": self.zones,
            "min_confidence": self.min_confidence,
            "min_occupancy": self.min_occupancy,
            "min_dwell_sec": self.min_dwell_sec,
            "debounce_sec": self.debounce_sec,
            "suppression_sec": self.suppression_sec,
            "target_severity": self.target_severity.value if self.target_severity else None,
        }


@dataclass(slots=True)
class EscalationPolicy:
    """Escalation rule for unacknowledged alarms."""

    policy_id: str
    name: str
    unacknowledged_timeout_sec: float = 300.0
    escalate_severity: bool = True
    repeat_notification_sec: float = 600.0
    auto_create_incident: bool = True


@dataclass(slots=True)
class NotificationMessage:
    """Dispatch payload for notification channels."""

    notification_id: str
    channel_type: str
    target: str
    alarm_id: str
    title: str
    body: str
    sent_at: float = field(default_factory=time.time)
    status: str = "PENDING"
    incident_id: Optional[str] = None


@dataclass(slots=True)
class EvidencePackage:
    """Forensic investigation evidence package."""

    package_id: str
    incident_id: str
    created_at: float = field(default_factory=time.time)
    title: str = ""
    summary: str = ""
    event_timeline: list[dict[str, Any]] = field(default_factory=list)
    snapshots: list[str] = field(default_factory=list)
    recordings: list[dict[str, Any]] = field(default_factory=list)
    operator_audit_logs: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "package_id": self.package_id,
            "incident_id": self.incident_id,
            "created_at": round(self.created_at, 3),
            "title": self.title,
            "summary": self.summary,
            "event_timeline": self.event_timeline,
            "snapshots": self.snapshots,
            "recordings": self.recordings,
            "operator_audit_logs": self.operator_audit_logs,
        }
