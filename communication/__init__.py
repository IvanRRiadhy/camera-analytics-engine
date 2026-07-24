"""
Event Communication Layer Package.

Provides high-throughput, non-blocking, transport-agnostic, plugin-based event communication
and publishing infrastructure for external integrations (Log, MQTT, WebSocket, Kafka, RabbitMQ).
"""

from camera_analytics.communication.manager import (
    CommunicationManager,
    CommunicationMetrics,
)
from camera_analytics.communication.models import (
    AnalyticsEventSerializer,
    EventSeverity,
    StandardAnalyticsEvent,
)
from camera_analytics.communication.publisher_base import EventPublisher
from camera_analytics.communication.publisher_manager import PublisherManager
from camera_analytics.communication.publishers.log_publisher import LogPublisher
from camera_analytics.communication.publishers.mqtt_publisher import MQTTPublisher
from camera_analytics.communication.registry import (
    PublisherRegistry,
    register_publisher,
)

__all__ = [
    "StandardAnalyticsEvent",
    "EventSeverity",
    "AnalyticsEventSerializer",
    "EventPublisher",
    "PublisherRegistry",
    "register_publisher",
    "PublisherManager",
    "CommunicationManager",
    "CommunicationMetrics",
    "LogPublisher",
    "MQTTPublisher",
]
