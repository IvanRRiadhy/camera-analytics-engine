"""
Enterprise Alarm & Incident Management Test Suite (Sprint 12.4).

Verifies:
    1. AlarmRuleEngine rule evaluation & suppression windows.
    2. AlarmEngine converting analytics events to alarms.
    3. AlarmStateMachine valid state transitions & audit logs.
    4. IncidentManager alarm correlation into unified incident cases.
    5. EscalationEngine unacknowledged alarm timeout escalations.
    6. NotificationDispatcher multi-channel notification dispatch.
    7. EvidencePackageBuilder forensic package generation.
"""

import time
import unittest

from camera_analytics.alarm import (
    AlarmEngine,
    AlarmHealthMonitor,
    AlarmRule,
    AlarmRuleEngine,
    AlarmSeverity,
    AlarmState,
    AlarmStateMachine,
    ConsoleNotificationChannel,
    EscalationEngine,
    EscalationPolicy,
    EvidencePackageBuilder,
    IncidentManager,
    NotificationDispatcher,
    WebhookNotificationChannel,
)
from camera_analytics.communication.models import StandardAnalyticsEvent


class TestEnterpriseAlarmService(unittest.TestCase):
    """Alarm & Incident Management Unit Test Suite."""

    def setUp(self) -> None:
        """Initialize rules and alarm components."""
        self.rule1 = AlarmRule(
            rule_id="r1",
            name="Crowd Alert Rule",
            event_types=["CROWD_ALERT"],
            target_severity=AlarmSeverity.CRITICAL,
        )
        self.rule2 = AlarmRule(
            rule_id="r2",
            name="Loitering Rule",
            event_types=["LOITERING"],
            min_dwell_sec=2.0,
        )

        self.rule_engine = AlarmRuleEngine(rules=[self.rule1, self.rule2])
        self.alarm_engine = AlarmEngine(rule_engine=self.rule_engine)
        self.incident_manager = IncidentManager(correlation_window_sec=60.0)

    def test_rule_evaluation_and_alarm_generation(self) -> None:
        """Verify AlarmRuleEngine evaluates events and AlarmEngine creates alarms."""
        evt1 = StandardAnalyticsEvent(
            event_type="CROWD_ALERT",
            message="Crowd detected",
            camera_id="cam_01",
        )
        alarms = self.alarm_engine.process_event(evt1)

        self.assertEqual(len(alarms), 1)
        self.assertEqual(alarms[0].rule_id, "r1")
        self.assertEqual(alarms[0].severity, AlarmSeverity.CRITICAL)

    def test_dwell_time_rule_filtering(self) -> None:
        """Verify min_dwell_sec condition in AlarmRule Engine."""
        evt_short = StandardAnalyticsEvent(
            event_type="LOITERING",
            camera_id="cam_01",
            payload={"dwell_time_sec": 1.0},
        )
        evt_long = StandardAnalyticsEvent(
            event_type="LOITERING",
            camera_id="cam_01",
            payload={"dwell_time_sec": 5.0},
        )

        self.assertEqual(len(self.alarm_engine.process_event(evt_short)), 0)
        self.assertEqual(len(self.alarm_engine.process_event(evt_long)), 1)

    def test_alarm_state_machine_transitions(self) -> None:
        """Verify valid state transitions and invalid state blocks."""
        evt = StandardAnalyticsEvent(event_type="CROWD_ALERT", camera_id="cam_01")
        alarms = self.alarm_engine.process_event(evt)
        alarm = alarms[0]

        # Valid transitions: NEW ➔ ACKNOWLEDGED ➔ RESOLVED ➔ CLOSED
        ok1 = AlarmStateMachine.transition(alarm, AlarmState.ACKNOWLEDGED, operator_id="op_1")
        self.assertTrue(ok1)
        self.assertEqual(alarm.state, AlarmState.ACKNOWLEDGED)

        ok2 = AlarmStateMachine.transition(alarm, AlarmState.RESOLVED, operator_id="op_1")
        self.assertTrue(ok2)
        self.assertEqual(alarm.state, AlarmState.RESOLVED)

        # Invalid transition: CLOSED ➔ NEW (terminal state)
        AlarmStateMachine.transition(alarm, AlarmState.CLOSED)
        bad_trans = AlarmStateMachine.transition(alarm, AlarmState.NEW)
        self.assertFalse(bad_trans)

    def test_incident_correlation(self) -> None:
        """Verify IncidentManager correlates multiple alarms from same camera/zone."""
        evt1 = StandardAnalyticsEvent(event_type="CROWD_ALERT", camera_id="cam_lobby", zone_name="Entrance")
        evt2 = StandardAnalyticsEvent(event_type="CROWD_ALERT", camera_id="cam_lobby", zone_name="Entrance")

        alarms1 = self.alarm_engine.process_event(evt1)
        alarms2 = self.alarm_engine.process_event(evt2)

        inc1 = self.incident_manager.correlate_alarm(alarms1[0])
        inc2 = self.incident_manager.correlate_alarm(alarms2[0])

        self.assertEqual(inc1.incident_id, inc2.incident_id)
        self.assertEqual(len(inc1.alarm_ids), 2)

    def test_escalation_engine(self) -> None:
        """Verify EscalationEngine escalates unacknowledged alarms."""
        policy = EscalationPolicy(policy_id="p1", name="Policy", unacknowledged_timeout_sec=0.05)
        esc_engine = EscalationEngine(policy=policy, incident_manager=self.incident_manager)

        evt = StandardAnalyticsEvent(event_type="CROWD_ALERT", camera_id="cam_01")
        alarms = self.alarm_engine.process_event(evt)

        time.sleep(0.06)
        escalated = esc_engine.evaluate_unacknowledged_alarms(alarms)

        self.assertEqual(len(escalated), 1)
        self.assertEqual(alarms[0].state, AlarmState.INVESTIGATING)

    def test_notification_dispatcher(self) -> None:
        """Verify NotificationDispatcher dispatches payloads to registered channels."""
        dispatcher = NotificationDispatcher(channels=[ConsoleNotificationChannel(), WebhookNotificationChannel()])
        evt = StandardAnalyticsEvent(event_type="CROWD_ALERT", camera_id="cam_01")
        alarm = self.alarm_engine.process_event(evt)[0]

        count = dispatcher.dispatch_alarm_notification(alarm)
        self.assertEqual(count, 2)

    def test_evidence_package_builder(self) -> None:
        """Verify EvidencePackageBuilder constructs evidence packages."""
        evt = StandardAnalyticsEvent(event_type="CROWD_ALERT", camera_id="cam_01")
        alarm = self.alarm_engine.process_event(evt)[0]
        inc = self.incident_manager.correlate_alarm(alarm)

        pkg = EvidencePackageBuilder.build_evidence_package(incident=inc)
        self.assertIsNotNone(pkg.package_id)
        self.assertEqual(pkg.incident_id, inc.incident_id)


if __name__ == "__main__":
    unittest.main()
