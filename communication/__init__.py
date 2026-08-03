"""
Event Communication Layer Package.

Provides high-throughput, non-blocking, transport-agnostic, plugin-based event communication
and publishing infrastructure for external integrations (Log, MQTT, REST Webhook, Console, RabbitMQ).
"""

from camera_analytics.communication.manager import (
    CommunicationManager,
    CommunicationMetrics,
)
from camera_analytics.communication.models import (
    AnalyticsEventSerializer,
    EventDetailLevel,
    EventSeverity,
    StandardAnalyticsEvent,
)
from camera_analytics.communication.publisher_base import EventPublisher
from camera_analytics.communication.publisher_manager import PublisherManager
from camera_analytics.communication.publishers.console_publisher import ConsolePublisher
from camera_analytics.communication.publishers.log_publisher import LogPublisher
from camera_analytics.communication.publishers.mqtt_publisher import MQTTPublisher
from camera_analytics.communication.publishers.rabbitmq_publisher import RabbitMQPublisher
from camera_analytics.communication.publishers.rest_publisher import RestPublisher
from camera_analytics.communication.registry import (
    PublisherRegistry,
    register_publisher,
)
from camera_analytics.communication.router import EventRouter, EventRoutingRule

__all__ = [
    "StandardAnalyticsEvent",
    "EventSeverity",
    "EventDetailLevel",
    "AnalyticsEventSerializer",
    "EventPublisher",
    "PublisherRegistry",
    "register_publisher",
    "PublisherManager",
    "CommunicationManager",
    "CommunicationMetrics",
    "EventRouter",
    "EventRoutingRule",
    "LogPublisher",
    "MQTTPublisher",
    "RabbitMQPublisher",
    "RestPublisher",
    "ConsolePublisher",
]
