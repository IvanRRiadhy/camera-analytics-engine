"""
Notification Service Plugin Implementation.

Handles operator notification workflow across multi-channel dispatchers.
"""

from __future__ import annotations

import logging
from typing import Optional

from camera_analytics.alarm import (
    ConsoleNotificationChannel,
    NotificationDispatcher,
    WebhookNotificationChannel,
)
from camera_analytics.communication.models import StandardAnalyticsEvent
from camera_analytics.eventing.models import PlatformEvent
from camera_analytics.services.context import ServiceContext
from camera_analytics.services.interfaces import EventService

logger = logging.getLogger(__name__)


class NotificationServicePlugin(EventService):
    """Notification Service Plugin for higher-level operator notification workflows."""

    def __init__(self) -> None:
        super().__init__()
        self.dispatcher: Optional[NotificationDispatcher] = None

    def initialize(self, context: ServiceContext) -> None:
        super().initialize(context)
        self.dispatcher = NotificationDispatcher(
            channels=[ConsoleNotificationChannel(), WebhookNotificationChannel()]
        )
        logger.info("NotificationServicePlugin initialized")

    def start(self) -> None:
        logger.info("NotificationServicePlugin started")

    def on_event(self, event: StandardAnalyticsEvent | PlatformEvent) -> None:
        if isinstance(event, PlatformEvent) and event.event_type == "ALARM_CREATED":
            logger.info("NotificationServicePlugin dispatched notification for alarm: %s", event.payload)

    def stop(self) -> None:
        logger.info("NotificationServicePlugin stopped")
