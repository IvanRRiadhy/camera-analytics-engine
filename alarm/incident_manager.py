"""
Incident Manager Subsystem Implementation.

Groups related alarms into unified `Incident` cases within a correlation time window
(e.g. 60 seconds), maintaining complete event and alarm history.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Optional

from camera_analytics.alarm.schema import Alarm, AlarmSeverity, AlarmState, Incident

logger = logging.getLogger(__name__)


class IncidentManager:
    """Groups related Alarms into consolidated Incident cases."""

    def __init__(self, correlation_window_sec: float = 60.0) -> None:
        self.correlation_window_sec = correlation_window_sec
        self.incidents: dict[str, Incident] = {}

    def correlate_alarm(self, alarm: Alarm) -> Incident:
        """Correlate an alarm into an active incident or create a new incident case.

        Args:
            alarm: Incoming Alarm instance.

        Returns:
            Associated or created Incident instance.
        """
        now = time.time()

        # Check for active incident matching camera_id & zone within correlation window
        for inc in self.incidents.values():
            if inc.state in [AlarmState.NEW, AlarmState.ACKNOWLEDGED, AlarmState.INVESTIGATING]:
                if inc.camera_id == alarm.camera_id and (inc.zone_id == alarm.zone_id or not inc.zone_id):
                    if (now - inc.updated_at) <= self.correlation_window_sec:
                        inc.alarm_ids.append(alarm.alarm_id)
                        inc.event_ids.append(alarm.event_id)
                        inc.updated_at = now
                        # Upgrade severity if incoming alarm severity is higher
                        if self._severity_val(alarm.severity) > self._severity_val(inc.severity):
                            inc.severity = alarm.severity
                        logger.info("IncidentManager correlated alarm '%s' into incident '%s'", alarm.alarm_id, inc.incident_id)
                        return inc

        # Create new Incident
        inc_id = f"inc_{uuid.uuid4().hex[:8]}"
        title = f"Incident: {alarm.event_type} on {alarm.camera_id}"
        if alarm.zone_id:
            title += f" ({alarm.zone_id})"

        new_inc = Incident(
            incident_id=inc_id,
            title=title,
            camera_id=alarm.camera_id,
            zone_id=alarm.zone_id,
            severity=alarm.severity,
            state=AlarmState.NEW,
            created_at=now,
            updated_at=now,
            alarm_ids=[alarm.alarm_id],
            event_ids=[alarm.event_id],
            summary=f"Incident opened due to {alarm.message}",
        )

        self.incidents[inc_id] = new_inc
        logger.info("IncidentManager created new incident '%s': %s", inc_id, title)
        return new_inc

    def _severity_val(self, sev: AlarmSeverity) -> int:
        mapping = {AlarmSeverity.INFO: 1, AlarmSeverity.WARNING: 2, AlarmSeverity.ALERT: 3, AlarmSeverity.CRITICAL: 4}
        return mapping.get(sev, 1)

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        """Get incident by ID."""
        return self.incidents.get(incident_id)
