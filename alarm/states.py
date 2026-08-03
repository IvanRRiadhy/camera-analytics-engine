"""
Alarm State Machine Implementation.

Manages lifecycle states (NEW ➔ ACKNOWLEDGED ➔ INVESTIGATING ➔ RESOLVED ➔ CLOSED),
enforcing valid transitions and recording operator audit actions.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Optional

from camera_analytics.alarm.schema import Alarm, AlarmState, OperatorAction

logger = logging.getLogger(__name__)


class AlarmStateMachine:
    """State transition validator and audit trail recorder for Alarms."""

    VALID_TRANSITIONS: dict[AlarmState, list[AlarmState]] = {
        AlarmState.NEW: [AlarmState.ACKNOWLEDGED, AlarmState.INVESTIGATING, AlarmState.CLOSED],
        AlarmState.ACKNOWLEDGED: [AlarmState.INVESTIGATING, AlarmState.RESOLVED, AlarmState.CLOSED],
        AlarmState.INVESTIGATING: [AlarmState.RESOLVED, AlarmState.CLOSED],
        AlarmState.RESOLVED: [AlarmState.CLOSED, AlarmState.INVESTIGATING],
        AlarmState.CLOSED: [],  # Terminal state
    }

    @classmethod
    def transition(
        cls,
        alarm: Alarm,
        target_state: AlarmState,
        operator_id: str = "system",
        note: str = "",
    ) -> bool:
        """Perform state transition for an alarm if valid according to state machine rules.

        Args:
            alarm: Target Alarm instance.
            target_state: Desired AlarmState enum value.
            operator_id: ID of operator or system executing transition.
            note: Optional transition note or audit log text.

        Returns:
            True if transition succeeded, False if invalid.
        """
        current_state = alarm.state
        if current_state == target_state:
            return True

        allowed = cls.VALID_TRANSITIONS.get(current_state, [])
        if target_state not in allowed:
            logger.warning(
                "Invalid alarm state transition for '%s': %s ➔ %s (Allowed: %s)",
                alarm.alarm_id,
                current_state.value,
                target_state.value,
                [s.value for s in allowed],
            )
            return False

        now = time.time()
        alarm.state = target_state

        if target_state == AlarmState.ACKNOWLEDGED and not alarm.acknowledged_at:
            alarm.acknowledged_at = now
            alarm.assigned_operator = operator_id
        elif target_state == AlarmState.RESOLVED:
            alarm.resolved_at = now
        elif target_state == AlarmState.CLOSED:
            alarm.closed_at = now

        action = OperatorAction(
            action_id=f"act_{uuid.uuid4().hex[:6]}",
            alarm_id=alarm.alarm_id,
            operator_id=operator_id,
            action_type=f"TRANSITION_TO_{target_state.value}",
            timestamp=now,
            note=note,
        )
        alarm.history.append(action)

        logger.info(
            "Alarm '%s' transitioned: %s ➔ %s by '%s'",
            alarm.alarm_id,
            current_state.value,
            target_state.value,
            operator_id,
        )
        return True
