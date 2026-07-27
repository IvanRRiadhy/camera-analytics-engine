"""
RabbitMQ AMQP Network Event Publisher for camera_analytics framework.

Subclass of EventPublisher that publishes serialized messages to a RabbitMQ Topic Exchange.
Uses pika library with background fallback.
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Any, Optional

from camera_analytics.communication.models import StandardAnalyticsEvent
from camera_analytics.communication.publisher_base import EventPublisher
from camera_analytics.communication.registry import PublisherRegistry

logger = logging.getLogger(__name__)


@PublisherRegistry.register("rabbitmq")
class RabbitMQPublisher(EventPublisher):
    """Event Publisher that broadcasts events and registration messages to RabbitMQ Topic Exchanges.

    Args:
        name: Publisher instance identifier.
        enabled: Whether publisher is enabled.
        host: RabbitMQ Host.
        port: RabbitMQ Port.
        vhost: Virtual host.
        username: Username for authentication.
        password: Password for authentication.
    """

    def __init__(
        self,
        name: str = "rabbitmq",
        enabled: bool = True,
        host: str = "localhost",
        port: int = 5672,
        vhost: str = "cctv_vhost",
        username: str = "cctv_admin",
        password: str = "SecureCctvPass123",
    ) -> None:
        super().__init__(name=name, enabled=enabled)
        self._host = host
        self._port = port
        self._vhost = vhost
        self._username = username
        self._password = password

        self._pika: Any = None
        self._connection: Any = None
        self._channel: Any = None
        self._lock = threading.Lock()

    def on_initialize(self, config: dict[str, Any]) -> None:
        """Initialize RabbitMQ configuration."""
        self._host = config.get("host", self._host)
        self._port = config.get("port", self._port)
        self._vhost = config.get("vhost", self._vhost)
        self._username = config.get("username", self._username)
        self._password = config.get("password", self._password)

    def on_start(self) -> None:
        """Connect to RabbitMQ broker."""
        try:
            import pika
            self._pika = pika
        except ImportError:
            logger.warning("RabbitMQPublisher '%s': 'pika' package not installed. Operating in mock fallback mode.", self.name)
            self._is_healthy = False
            return

        try:
            credentials = self._pika.PlainCredentials(self._username, self._password)
            parameters = self._pika.ConnectionParameters(
                host=self._host,
                port=self._port,
                virtual_host=self._vhost,
                credentials=credentials
            )
            self._connection = self._pika.BlockingConnection(parameters)
            self._channel = self._connection.channel()
            self._channel.confirm_delivery()
            self._is_healthy = True
            logger.info("RabbitMQPublisher '%s' connected to %s:%d (vhost: %s)", self.name, self._host, self._port, self._vhost)
        except Exception as exc:
            self._is_healthy = False
            logger.error("RabbitMQPublisher '%s' failed to connect: %s", self.name, exc)

    def publish_raw(self, exchange: str, routing_key: str, payload_dict: dict[str, Any]) -> bool:
        """Publish a raw payload dictionary to a specific exchange and routing key."""
        if not self._is_running or not self._enabled:
            return False

        payload_str = json.dumps(payload_dict)

        if self._channel is None or self._pika is None:
            logger.debug("RabbitMQPublisher [Fallback Mock] Exchange '%s' Key '%s': %s", exchange, routing_key, payload_str[:100])
            return True

        try:
            # Declare exchange idempotently before publishing
            self._channel.exchange_declare(exchange=exchange, exchange_type="topic", durable=True)

            properties = self._pika.BasicProperties(
                content_type="application/json",
                content_encoding="utf-8",
                delivery_mode=2,
                headers={
                    "x-message-version": "1.0.0",
                    "x-tenant-id": payload_dict.get("applicationId", "")
                }
            )
            self._channel.basic_publish(
                exchange=exchange,
                routing_key=routing_key,
                body=payload_str,
                properties=properties
            )
            logger.info("RabbitMQPublisher '%s' published to '%s'/'%s'", self.name, exchange, routing_key)
            return True
        except Exception as exc:
            self._is_healthy = False
            logger.error("RabbitMQPublisher '%s' publish failed: %s", self.name, exc)
            return False

    def publish(self, event: StandardAnalyticsEvent, serialized_payload: str) -> bool:
        """Publish standard analytics event."""
        payload_dict = json.loads(serialized_payload)
        return self.publish_raw(exchange="cctv.analytics", routing_key="analytics.event", payload_dict=payload_dict)

    def on_stop(self) -> None:
        with self._lock:
            if self._connection is not None and self._connection.is_open:
                try:
                    self._connection.close()
                except Exception:
                    pass
                self._connection = None
                self._channel = None
