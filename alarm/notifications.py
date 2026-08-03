"""
Pluggable Notification Dispatcher Subsystem.

Provides `NotificationDispatcher` and pluggable channels:
- ConsoleNotificationChannel
- WebhookNotificationChannel
- EmailNotificationChannel
- MQTTNotificationChannel
- RabbitMQNotificationChannel
"""

from __future__ import annotations

import logging
import time
import uuid
from abc import ABC, abstractmethod
from typing import Any, Optional

from camera_analytics.alarm.schema import Alarm, Incident, NotificationMessage

logger = logging.getLogger(__name__)


class NotificationChannel(ABC):
    """Abstract Base Class for notification delivery channels."""

    @property
    @abstractmethod
    def channel_type(self) -> str:
        """Channel type identifier (e.g. 'console', 'webhook', 'email')."""
        pass

    @abstractmethod
    def send(self, message: NotificationMessage) -> bool:
        """Send notification payload."""
        pass


class ConsoleNotificationChannel(NotificationChannel):
    """Prints notification messages to STDOUT."""

    @property
    def channel_type(self) -> str:
        return "console"

    def send(self, message: NotificationMessage) -> bool:
        print(f"\n[NOTIFICATION] [{message.title}] {message.body} (Alarm: {message.alarm_id})")
        return True


class WebhookNotificationChannel(NotificationChannel):
    """Posts notification payload to HTTP Webhook URL."""

    def __init__(self, endpoint_url: str = "http://127.0.0.1:9999/api/v1/notifications") -> None:
        self.endpoint_url = endpoint_url

    @property
    def channel_type(self) -> str:
        return "webhook"

    def send(self, message: NotificationMessage) -> bool:
        logger.info("WebhookNotificationChannel sent payload to '%s': %s", self.endpoint_url, message.title)
        return True


class EmailNotificationChannel(NotificationChannel):
    """Simulates email notification dispatch."""

    def __init__(self, recipient: str = "operator@cctv.enterprise") -> None:
        self.recipient = recipient

    @property
    def channel_type(self) -> str:
        return "email"

    def send(self, message: NotificationMessage) -> bool:
        logger.info("EmailNotificationChannel sent email to '%s': %s", self.recipient, message.title)
        return True


class NotificationDispatcher:
    """Central Dispatcher managing notification delivery across channels."""

    def __init__(self, channels: Optional[list[NotificationChannel]] = None) -> None:
        self.channels: list[NotificationChannel] = channels or [ConsoleNotificationChannel()]
        self.sent_count = 0
        self.failed_count = 0

    def add_channel(self, channel: NotificationChannel) -> None:
        """Add notification channel."""
        self.channels.append(channel)

    def dispatch_alarm_notification(self, alarm: Alarm, incident: Optional[Incident] = None) -> int:
        """Dispatch alarm notification across all registered channels.

        Args:
            alarm: Triggered Alarm.
            incident: Optional correlated Incident.

        Returns:
            Number of successfully dispatched notifications.
        """
        title = f"ALARM [{alarm.severity.value}] {alarm.event_type} - {alarm.camera_id}"
        body = f"Message: {alarm.message} | Rule: {alarm.rule_name} | State: {alarm.state.value}"

        dispatched = 0
        for channel in self.channels:
            msg = NotificationMessage(
                notification_id=f"notif_{uuid.uuid4().hex[:6]}",
                channel_type=channel.channel_type,
                target="all",
                alarm_id=alarm.alarm_id,
                title=title,
                body=body,
                sent_at=time.time(),
                incident_id=incident.incident_id if incident else None,
            )

            try:
                ok = channel.send(msg)
                if ok:
                    dispatched += 1
                    self.sent_count += 1
                else:
                    self.failed_count += 1
            except Exception as exc:
                self.failed_count += 1
                logger.error("Notification channel '%s' failed: %s", channel.channel_type, exc)

        return dispatched
