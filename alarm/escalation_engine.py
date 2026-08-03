"""
Escalation Engine Implementation.

Evaluates escalation policies for unacknowledged alarms and incidents (timeouts, severity escalation, auto-incidents).
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from camera_analytics.alarm.incident_manager import IncidentManager
from camera_analytics.alarm.schema import Alarm, AlarmSeverity, AlarmState, EscalationPolicy
from camera_analytics.alarm.states import AlarmStateMachine

logger = logging.getLogger(__name__)


class EscalationEngine:
    """Evaluates unacknowledged alarms against escalation policies."""

    def __init__(
        self,
        policy: Optional[EscalationPolicy] = None,
        incident_manager: Optional[IncidentManager] = None,
    ) -> None:
        self.policy = policy or EscalationPolicy(policy_id="default_esc", name="Default Policy")
        self.incident_manager = incident_manager
        self.escalation_count = 0

    def evaluate_unacknowledged_alarms(self, active_alarms: list[Alarm]) -> list[Alarm]:
        """Check active alarms for unacknowledged timeout and trigger escalations.

        Args:
            active_alarms: List of active Alarm instances.

        Returns:
            List of alarms that were escalated.
        """
        now = time.time()
        escalated_alarms: list[Alarm] = []

        for alarm in active_alarms:
            if alarm.state == AlarmState.NEW:
                unack_sec = now - alarm.created_at
                if unack_sec >= self.policy.unacknowledged_timeout_sec:
                    # Escalate severity if configured
                    if self.policy.escalate_severity and alarm.severity != AlarmSeverity.CRITICAL:
                        alarm.severity = AlarmSeverity.CRITICAL
                        logger.warning("EscalationEngine: Escalated alarm '%s' severity to CRITICAL (unack=%.1fs)", alarm.alarm_id, unack_sec)

                    # Trigger state transition audit
                    AlarmStateMachine.transition(alarm, AlarmState.INVESTIGATING, operator_id="escalation_system", note="Auto-escalated due to unacknowledged timeout")

                    # Auto-create incident if configured
                    if self.policy.auto_create_incident and self.incident_manager:
                        self.incident_manager.correlate_alarm(alarm)

                    self.escalation_count += 1
                    escalated_alarms.append(alarm)

        return escalated_alarms
