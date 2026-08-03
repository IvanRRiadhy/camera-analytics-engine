"""
Controlled Publishers Package Manifest.

Explicitly imports and exposes built-in EventPublisher implementations for PublisherRegistry controlled discovery.
"""

from camera_analytics.communication.publishers.console_publisher import ConsolePublisher
from camera_analytics.communication.publishers.log_publisher import LogPublisher
from camera_analytics.communication.publishers.mqtt_publisher import MQTTPublisher
from camera_analytics.communication.publishers.rabbitmq_publisher import RabbitMQPublisher
from camera_analytics.communication.publishers.rest_publisher import RestPublisher

__all__ = [
    "ConsolePublisher",
    "LogPublisher",
    "MQTTPublisher",
    "RabbitMQPublisher",
    "RestPublisher",
]
