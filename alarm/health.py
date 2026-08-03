"""
Alarm & Incident Health Monitoring Subsystem.

Tracks active alarms, active incidents, MTTA (Mean Time To Acknowledge),
MTTR (Mean Time To Resolve), notification success rates, and escalation statistics.
"""

from __future__ import annotations

import logging
from typing import Any

from camera_analytics.alarm.alarm_engine import AlarmEngine
from camera_analytics.alarm.escalation_engine import EscalationEngine
from camera_analytics.alarm.incident_manager import IncidentManager
from camera_analytics.alarm.notifications import NotificationDispatcher
from camera_analytics.alarm.schema import AlarmState

logger = logging.getLogger(__name__)


class AlarmHealthMonitor:
    """Observability & Health Monitoring Subsystem for Alarms and Incidents."""

    def __init__(
        self,
        alarm_engine: AlarmEngine,
        incident_manager: IncidentManager,
        escalation_engine: EscalationEngine,
        notification_dispatcher: NotificationDispatcher,
    ) -> None:
        self.alarm_engine = alarm_engine
        self.incident_manager = incident_manager
        self.escalation_engine = escalation_engine
        self.dispatcher = notification_dispatcher

    def get_health_report(self) -> dict[str, Any]:
        """Generate observable health report."""
        alarms = self.alarm_engine.generated_alarms
        incidents = list(self.incident_manager.incidents.values())

        active_alarms = [a for a in alarms if a.state in [AlarmState.NEW, AlarmState.ACKNOWLEDGED, AlarmState.INVESTIGATING]]
        active_incidents = [i for i in incidents if i.state in [AlarmState.NEW, AlarmState.ACKNOWLEDGED, AlarmState.INVESTIGATING]]

        # Calculate MTTA & MTTR
        ack_times = [a.acknowledged_at - a.created_at for a in alarms if a.acknowledged_at]
        mtta_sec = sum(ack_times) / len(ack_times) if ack_times else 0.0

        res_times = [a.resolved_at - a.created_at for a in alarms if a.resolved_at]
        mttr_sec = sum(res_times) / len(res_times) if res_times else 0.0

        tot_notif = self.dispatcher.sent_count + self.dispatcher.failed_count
        success_rate = (self.dispatcher.sent_count / tot_notif * 100.0) if tot_notif > 0 else 100.0

        return {
            "alarms": {
                "total_generated": len(alarms),
                "active_count": len(active_alarms),
                "closed_count": len(alarms) - len(active_alarms),
            },
            "incidents": {
                "total_incidents": len(incidents),
                "active_count": len(active_incidents),
            },
            "performance": {
                "mtta_sec": round(mtta_sec, 2),
                "mttr_sec": round(mttr_sec, 2),
                "escalation_count": self.escalation_engine.escalation_count,
                "notification_sent": self.dispatcher.sent_count,
                "notification_failed": self.dispatcher.failed_count,
                "notification_success_rate_pct": round(success_rate, 1),
            },
        }
