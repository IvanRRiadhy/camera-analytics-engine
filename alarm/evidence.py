"""
Forensic Evidence Package Builder.

Generates structured forensic investigation packages containing incident summaries,
event timelines, snapshots, recording references, playback seek offsets, and operator audit logs.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Optional

from camera_analytics.alarm.schema import EvidencePackage, Incident

logger = logging.getLogger(__name__)


class EvidencePackageBuilder:
    """Constructs complete evidence packages for incident investigation and case management."""

    @staticmethod
    def build_evidence_package(
        incident: Incident,
        event_timeline: Optional[list[dict[str, Any]]] = None,
        snapshots: Optional[list[str]] = None,
        recordings: Optional[list[dict[str, Any]]] = None,
        operator_audit_logs: Optional[list[dict[str, Any]]] = None,
    ) -> EvidencePackage:
        """Build an EvidencePackage dataclass for an incident.

        Args:
            incident: Incident instance.
            event_timeline: List of formatted timeline entries.
            snapshots: List of snapshot file paths.
            recordings: List of video segment playback references.
            operator_audit_logs: List of operator audit action dicts.

        Returns:
            EvidencePackage dataclass instance.
        """
        pkg_id = f"evid_{incident.incident_id[:8]}_{int(time.time())}"
        summary = (
            f"Evidence package for Incident '{incident.incident_id}' ({incident.title}). "
            f"Contains {len(incident.alarm_ids)} alarms and {len(incident.event_ids)} analytics events."
        )

        pkg = EvidencePackage(
            package_id=pkg_id,
            incident_id=incident.incident_id,
            created_at=time.time(),
            title=f"Evidence Case: {incident.title}",
            summary=summary,
            event_timeline=event_timeline or [],
            snapshots=snapshots or [],
            recordings=recordings or [],
            operator_audit_logs=operator_audit_logs or [],
        )

        logger.info("EvidencePackageBuilder created package '%s' for incident '%s'", pkg_id, incident.incident_id)
        return pkg
