"""
Enterprise Standard Event JSON Output Provider implementation.
"""

from __future__ import annotations

import logging

from camera_analytics.communication.manager import CommunicationManager
from camera_analytics.communication.models import StandardAnalyticsEvent
from camera_analytics.output.base import OutputProvider

logger = logging.getLogger(__name__)


class EnterpriseEventOutputProvider(OutputProvider):
    """OutputProvider forwarding StandardAnalyticsEvents to CommunicationManager singleton."""

    def __init__(
        self,
        name: str = "enterprise_event",
        comm_manager: CommunicationManager | None = None,
        enabled: bool = True,
    ) -> None:
        super().__init__(name=name, enabled=enabled)
        self._comm_manager = comm_manager

    @property
    def comm_manager(self) -> CommunicationManager:
        if self._comm_manager is None:
            self._comm_manager = CommunicationManager.get_instance()
        return self._comm_manager

    def output(self, event: StandardAnalyticsEvent) -> bool:
        if not self._enabled:
            return False

        try:
            return self.comm_manager.enqueue(event)
        except Exception as exc:
            logger.error("EnterpriseEventOutputProvider failed to enqueue event: %s", exc)
            return False

    def flush(self) -> None:
        if self._comm_manager is not None:
            self._comm_manager.flush()
