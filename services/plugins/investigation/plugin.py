"""
Investigation Service Plugin Implementation.

Handles forensic evidence packaging and investigation query capabilities.
"""

from __future__ import annotations

import logging
from typing import Optional

from camera_analytics.communication.models import StandardAnalyticsEvent
from camera_analytics.eventing.models import PlatformEvent
from camera_analytics.services.context import ServiceContext
from camera_analytics.services.interfaces import EventService

logger = logging.getLogger(__name__)


class InvestigationServicePlugin(EventService):
    """Forensic Investigation Service Plugin."""

    def __init__(self) -> None:
        super().__init__()

    def initialize(self, context: ServiceContext) -> None:
        super().initialize(context)

        # Demonstrate lean dependency resolution via context & registry DI
        rec_service = context.get_service_dependency("recording")
        alarm_service = context.get_service_dependency("alarm")

        logger.info("InvestigationServicePlugin initialized (Dependencies resolved: rec=%s, alarm=%s)", bool(rec_service), bool(alarm_service))

    def start(self) -> None:
        logger.info("InvestigationServicePlugin started")

    def on_event(self, event: StandardAnalyticsEvent | PlatformEvent) -> None:
        if isinstance(event, PlatformEvent):
            logger.debug("InvestigationServicePlugin logged platform event: %s", event.event_type)

    def stop(self) -> None:
        logger.info("InvestigationServicePlugin stopped")
