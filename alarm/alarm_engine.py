"""
Alarm Engine Implementation.

Converts `StandardAnalyticsEvent` objects into `Alarm` instances using `AlarmRuleEngine`.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Optional

from camera_analytics.alarm.rule_engine import AlarmRuleEngine
from camera_analytics.alarm.schema import Alarm, AlarmRule, AlarmSeverity, AlarmState
from camera_analytics.communication.models import StandardAnalyticsEvent

logger = logging.getLogger(__name__)


class AlarmEngine:
    """Core Alarm Generation Engine transforming analytics events to actionable alarms."""

    def __init__(self, rule_engine: Optional[AlarmRuleEngine] = None) -> None:
        self.rule_engine = rule_engine or AlarmRuleEngine()
        self.generated_alarms: list[Alarm] = []

    def process_event(self, event: StandardAnalyticsEvent) -> list[Alarm]:
        """Process incoming analytics event and return generated alarms.

        Args:
            event: StandardAnalyticsEvent instance.

        Returns:
            List of generated Alarm instances.
        """
        matching_rules = self.rule_engine.evaluate_event(event)
        new_alarms: list[Alarm] = []

        for rule in matching_rules:
            sev_str = (rule.target_severity.value if rule.target_severity else event.severity).upper()
            try:
                sev_enum = AlarmSeverity[sev_str]
            except KeyError:
                sev_enum = AlarmSeverity.WARNING

            alarm = Alarm(
                alarm_id=f"alarm_{uuid.uuid4().hex[:8]}",
                rule_id=rule.rule_id,
                rule_name=rule.name,
                event_id=event.event_id,
                event_type=event.event_type,
                camera_id=event.camera_id,
                zone_id=event.zone_name or event.zone_id,
                severity=sev_enum,
                state=AlarmState.NEW,
                created_at=time.time(),
                track_id=event.track_id,
                snapshot_path=None,
                message=event.message or f"Alarm triggered by rule '{rule.name}'",
            )

            self.generated_alarms.append(alarm)
            new_alarms.append(alarm)
            logger.info("AlarmEngine generated alarm '%s' for camera '%s' (rule='%s')", alarm.alarm_id, alarm.camera_id, rule.name)

        return new_alarms
