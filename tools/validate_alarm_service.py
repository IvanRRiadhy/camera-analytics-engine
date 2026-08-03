"""
CLI Alarm & Incident Management Subsystem Validator & Benchmark Tool.

Validates rule evaluation, alarm generation, incident correlation, state transitions,
escalation policies, notification dispatching, evidence packaging, and prints benchmark reports.

Usage::

    python -m camera_analytics.tools.validate_alarm_service
"""

from __future__ import annotations

import argparse
import logging
import time

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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("validate_alarm_service")


def main() -> None:
    logger.info("================================================================================")
    logger.info("SPRINT 12.4 — ENTERPRISE ALARM & INCIDENT MANAGEMENT VALIDATION")
    logger.info("================================================================================")

    # 1. Configure Rule Engine
    rule1 = AlarmRule(
        rule_id="rule_crowd_critical",
        name="Critical Crowd Density Alert",
        event_types=["CROWD_ALERT"],
        target_severity=AlarmSeverity.CRITICAL,
        suppression_sec=0.0,
    )
    rule2 = AlarmRule(
        rule_id="rule_loitering_warning",
        name="Loitering Warning Alert",
        event_types=["LOITERING"],
        target_severity=AlarmSeverity.WARNING,
        suppression_sec=0.0,
    )
    rule3 = AlarmRule(
        rule_id="rule_zone_enter_info",
        name="Lobby Zone Enter Alert",
        event_types=["ZONE_ENTER"],
        target_severity=AlarmSeverity.INFO,
        suppression_sec=0.0,
    )

    rule_engine = AlarmRuleEngine(rules=[rule1, rule2, rule3])
    alarm_engine = AlarmEngine(rule_engine=rule_engine)
    incident_manager = IncidentManager(correlation_window_sec=60.0)

    escalation_policy = EscalationPolicy(
        policy_id="pol_urgent",
        name="Urgent Escalation Policy",
        unacknowledged_timeout_sec=0.1,  # Short timeout for instant test
        escalate_severity=True,
        auto_create_incident=True,
    )
    escalation_engine = EscalationEngine(policy=escalation_policy, incident_manager=incident_manager)

    dispatcher = NotificationDispatcher(
        channels=[ConsoleNotificationChannel(), WebhookNotificationChannel()]
    )

    health_mon = AlarmHealthMonitor(alarm_engine, incident_manager, escalation_engine, dispatcher)

    # 2. Simulate Event Stream
    sample_events = [
        StandardAnalyticsEvent(event_type="ZONE_ENTER", message="Person entered lobby", camera_id="cam_main_lobby", zone_name="Lobby", track_id=1),
        StandardAnalyticsEvent(event_type="LOITERING", message="Loitering detected near vault", camera_id="cam_main_lobby", zone_name="Lobby", track_id=2, severity="WARNING"),
        StandardAnalyticsEvent(event_type="CROWD_ALERT", message="Crowd threshold exceeded", camera_id="cam_main_lobby", zone_name="Lobby", severity="CRITICAL"),
    ]

    logger.info("Simulating event stream evaluation into Alarm Engine...")
    generated_alarms = []

    for evt in sample_events:
        alarms = alarm_engine.process_event(evt)
        for alarm in alarms:
            generated_alarms.append(alarm)
            # Correlate into Incident
            inc = incident_manager.correlate_alarm(alarm)
            # Dispatch Notifications
            dispatcher.dispatch_alarm_notification(alarm, inc)

    # 3. Simulate Operator State Transitions
    if generated_alarms:
        a0 = generated_alarms[0]
        AlarmStateMachine.transition(a0, AlarmState.ACKNOWLEDGED, operator_id="op_john", note="Checking live view")
        AlarmStateMachine.transition(a0, AlarmState.INVESTIGATING, operator_id="op_john", note="Dispatching security guard")
        AlarmStateMachine.transition(a0, AlarmState.RESOLVED, operator_id="op_john", note="False alarm cleared")

    # 4. Trigger Escalation Check
    time.sleep(0.15)
    escalation_engine.evaluate_unacknowledged_alarms(generated_alarms)

    # 5. Build Evidence Package for active incident
    all_incidents = list(incident_manager.incidents.values())
    evidence_pkg = None
    if all_incidents:
        inc_target = all_incidents[0]
        evidence_pkg = EvidencePackageBuilder.build_evidence_package(
            incident=inc_target,
            event_timeline=[{"timestamp": time.time(), "event": "Crowd alert recorded"}],
            snapshots=["snapshots/cam_main_lobby/20260728/snap_001.jpg"],
            recordings=[{"segment_id": "seg_001", "seek_offset_sec": 4.2}],
            operator_audit_logs=[a0.history[0].to_dict()] if generated_alarms else [],
        )

    # 6. Report Health Statistics
    health_report = health_mon.get_health_report()

    logger.info("================================================================================")
    logger.info("ALARM & INCIDENT MANAGEMENT BENCHMARK RESULTS")
    logger.info("================================================================================")
    logger.info("Total Alarms Generated:      %d alarms", health_report["alarms"]["total_generated"])
    logger.info("Active Alarms Remaining:     %d alarms", health_report["alarms"]["active_count"])
    logger.info("Total Incidents Correlated:  %d incidents", health_report["incidents"]["total_incidents"])
    logger.info("MTTA (Mean Time Acknowledge): %.3f sec", health_report["performance"]["mtta_sec"])
    logger.info("MTTR (Mean Time Resolve):     %.3f sec", health_report["performance"]["mttr_sec"])
    logger.info("Escalated Alarms Count:      %d escalations", health_report["performance"]["escalation_count"])
    logger.info("Notification Success Rate:   %.1f%%", health_report["performance"]["notification_success_rate_pct"])
    logger.info("--------------------------------------------------------------------------------")
    if evidence_pkg:
        logger.info("FORENSIC EVIDENCE PACKAGE GENERATED:")
        logger.info("  - Package ID:              %s", evidence_pkg.package_id)
        logger.info("  - Target Incident ID:      %s", evidence_pkg.incident_id)
        logger.info("  - Summary:                 %s", evidence_pkg.summary)
    logger.info("================================================================================")
    logger.info("Sprint 12.4 Enterprise Alarm & Incident Management validation complete.")


if __name__ == "__main__":
    main()
