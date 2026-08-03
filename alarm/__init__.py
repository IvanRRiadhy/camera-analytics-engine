"""
Enterprise Alarm & Incident Management Subsystem Package.

Transforms `StandardAnalyticsEvent` objects into actionable alarms, correlates related alarms
into incidents, manages state transitions, executes escalation policies, dispatches multi-channel
notifications, and packages forensic evidence.
"""

from camera_analytics.alarm.alarm_engine import AlarmEngine
from camera_analytics.alarm.escalation_engine import EscalationEngine
from camera_analytics.alarm.evidence import EvidencePackageBuilder
from camera_analytics.alarm.health import AlarmHealthMonitor
from camera_analytics.alarm.incident_manager import IncidentManager
from camera_analytics.alarm.notifications import (
    ConsoleNotificationChannel,
    EmailNotificationChannel,
    NotificationChannel,
    NotificationDispatcher,
    WebhookNotificationChannel,
)
from camera_analytics.alarm.rule_engine import AlarmRuleEngine
from camera_analytics.alarm.schema import (
    Alarm,
    AlarmRule,
    AlarmSeverity,
    AlarmState,
    EscalationPolicy,
    EvidencePackage,
    Incident,
    NotificationMessage,
    OperatorAction,
)
from camera_analytics.alarm.states import AlarmStateMachine

__all__ = [
    "AlarmState",
    "AlarmSeverity",
    "OperatorAction",
    "Alarm",
    "Incident",
    "AlarmRule",
    "EscalationPolicy",
    "NotificationMessage",
    "EvidencePackage",
    "AlarmStateMachine",
    "AlarmRuleEngine",
    "AlarmEngine",
    "IncidentManager",
    "EscalationEngine",
    "NotificationChannel",
    "ConsoleNotificationChannel",
    "WebhookNotificationChannel",
    "EmailNotificationChannel",
    "NotificationDispatcher",
    "EvidencePackageBuilder",
    "AlarmHealthMonitor",
]
