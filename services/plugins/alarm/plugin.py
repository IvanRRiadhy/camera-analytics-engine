"""
Alarm Service Plugin Implementation.

Wraps AlarmEngine, IncidentManager, and EscalationEngine into an EventService plugin,
and re-emits `ALARM_CREATED` PlatformEvents back to the Platform Event Bus.
"""

from __future__ import annotations

import logging
from typing import Optional

from camera_analytics.alarm import (
    AlarmEngine,
    AlarmRule,
    AlarmRuleEngine,
    AlarmSeverity,
    EscalationEngine,
    IncidentManager,
)
from camera_analytics.communication.models import StandardAnalyticsEvent
from camera_analytics.eventing.models import AlarmPayload, PlatformEvent
from camera_analytics.services.context import ServiceContext
from camera_analytics.services.interfaces import EventService

logger = logging.getLogger(__name__)


class AlarmServicePlugin(EventService):
    """Alarm & Incident Management Service Plugin."""

    def __init__(self) -> None:
        super().__init__()
        self.rule_engine: Optional[AlarmRuleEngine] = None
        self.alarm_engine: Optional[AlarmEngine] = None
        self.incident_manager: Optional[IncidentManager] = None
        self.escalation_engine: Optional[EscalationEngine] = None

    def initialize(self, context: ServiceContext) -> None:
        super().initialize(context)

        # Default rules
        rules = [
            AlarmRule(rule_id="r_crowd", name="Crowd Alert Rule", event_types=["CROWD_ALERT"], target_severity=AlarmSeverity.CRITICAL),
            AlarmRule(rule_id="r_loiter", name="Loitering Rule", event_types=["LOITERING"], target_severity=AlarmSeverity.WARNING),
            AlarmRule(rule_id="r_direction", name="Direction Rule", event_types=["DIRECTION_VIOLATION"], target_severity=AlarmSeverity.WARNING),
        ]

        self.rule_engine = AlarmRuleEngine(rules=rules)
        self.alarm_engine = AlarmEngine(rule_engine=self.rule_engine)

        corr_window = context.config.get("correlation_window_sec", 60.0)
        self.incident_manager = IncidentManager(correlation_window_sec=corr_window)
        self.escalation_engine = EscalationEngine(incident_manager=self.incident_manager)
        logger.info("AlarmServicePlugin initialized")

    def start(self) -> None:
        logger.info("AlarmServicePlugin started")

    def on_event(self, event: StandardAnalyticsEvent | PlatformEvent) -> None:
        if isinstance(event, StandardAnalyticsEvent) and self.alarm_engine and self.incident_manager:
            alarms = self.alarm_engine.process_event(event)
            for alarm in alarms:
                inc = self.incident_manager.correlate_alarm(alarm)

                # Re-emit secondary platform event back to event bus
                pe = PlatformEvent.create(
                    event_type="ALARM_CREATED",
                    payload=AlarmPayload(
                        alarm_id=alarm.alarm_id,
                        rule_id=alarm.rule_id,
                        camera_id=alarm.camera_id,
                        severity=alarm.severity.value,
                        state=alarm.state.value,
                        message=alarm.message,
                    ),
                    source="service.alarm",
                )
                self.emit_event(pe)

    def stop(self) -> None:
        logger.info("AlarmServicePlugin stopped")
