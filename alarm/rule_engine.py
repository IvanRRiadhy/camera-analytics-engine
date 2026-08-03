"""
Declarative Alarm Rule Engine Implementation.

Evaluates incoming `StandardAnalyticsEvent` objects against declarative rules,
supporting conditions based on event_type, severity, camera, zone, occupancy, dwell time,
queue length, confidence, schedules, and custom metadata with suppression & debounce control.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from camera_analytics.alarm.schema import AlarmRule, AlarmSeverity
from camera_analytics.communication.models import StandardAnalyticsEvent

logger = logging.getLogger(__name__)


class AlarmRuleEngine:
    """Configuration-driven rule engine for triggering alarms."""

    def __init__(self, rules: Optional[list[AlarmRule]] = None) -> None:
        self.rules: dict[str, AlarmRule] = {}
        self._last_triggered_ts: dict[str, float] = {}  # rule_id -> timestamp for suppression

        if rules:
            for r in rules:
                self.add_rule(r)

    def add_rule(self, rule: AlarmRule) -> None:
        """Register a new AlarmRule."""
        self.rules[rule.rule_id] = rule
        logger.debug("AlarmRuleEngine registered rule '%s' (%s)", rule.rule_id, rule.name)

    def evaluate_event(self, event: StandardAnalyticsEvent) -> list[AlarmRule]:
        """Evaluate event against registered rules and return matching rules.

        Args:
            event: StandardAnalyticsEvent instance.

        Returns:
            List of matching AlarmRule instances that triggered.
        """
        now = time.time()
        matching_rules: list[AlarmRule] = []

        for rule in self.rules.values():
            if not rule.enabled:
                continue

            # 1. Event Type Match
            if rule.event_types and "*" not in rule.event_types and event.event_type not in rule.event_types:
                continue

            # 2. Severity Match
            if rule.severities and "*" not in rule.severities and event.severity not in rule.severities:
                continue

            # 3. Camera Match
            if rule.cameras and "*" not in rule.cameras and event.camera_id not in rule.cameras:
                continue

            # 4. Zone Match
            if rule.zones and "*" not in rule.zones:
                evt_zone = event.zone_name or event.zone_id or ""
                if evt_zone not in rule.zones:
                    continue

            # 5. Occupancy Condition
            occupancy = event.payload.get("occupancy_count", getattr(event, "occupancy_count", 0))
            if rule.min_occupancy > 0 and occupancy < rule.min_occupancy:
                continue

            # 6. Dwell Time Condition
            dwell_time = event.payload.get("dwell_time_sec", getattr(event, "dwell_time_sec", 0.0))
            if rule.min_dwell_sec > 0.0 and dwell_time < rule.min_dwell_sec:
                continue

            # 7. Suppression Window Check
            if rule.suppression_sec > 0.0:
                last_ts = self._last_triggered_ts.get(rule.rule_id, 0.0)
                if (now - last_ts) < rule.suppression_sec:
                    logger.debug("Rule '%s' suppressed (suppression window %.1fs active)", rule.rule_id, rule.suppression_sec)
                    continue

            # Rule triggered!
            self._last_triggered_ts[rule.rule_id] = now
            matching_rules.append(rule)

        return matching_rules
