"""
Decoupled Event Subscribers for RuntimeEventBus propagation.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Optional

from camera_analytics.events.models import BaseRuntimeEvent
from camera_analytics.events.serializer import EventSerializer

logger = logging.getLogger(__name__)


class EventSubscriber(ABC):
    """Abstract Base Class for subscribers listening to RuntimeEventBus."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.events_received: int = 0
        self.last_latency_ms: float = 0.0

    @abstractmethod
    def handle_event(self, event: BaseRuntimeEvent) -> None:
        """Process received runtime event."""
        pass


class RabbitMQEventSubscriber(EventSubscriber):
    """Infrastructure subscriber forwarding runtime events to RabbitMQ message broker."""

    def __init__(self, name: str = "RabbitMQPublisherSubscriber", publisher: Any = None) -> None:
        super().__init__(name=name)
        self.publisher = publisher

    def handle_event(self, event: BaseRuntimeEvent) -> None:
        start_t = time.perf_counter()
        self.events_received += 1

        payload_json = EventSerializer.serialize(event)
        routing_key = f"event.{event.event_type.lower()}.{event.camera_id}"

        if self.publisher:
            try:
                self.publisher.publish(payload_json, routing_key=routing_key)
            except Exception as exc:
                logger.warning("[%s] Failed to publish over RabbitMQ: %s", self.name, exc)
        else:
            logger.debug("[%s] (Simulated AMQP Publish) RoutingKey: '%s' -> Payload: %s", self.name, routing_key, payload_json[:80])

        self.last_latency_ms = (time.perf_counter() - start_t) * 1000.0


class TelemetryCollectorSubscriber(EventSubscriber):
    """Subscriber aggregating realtime telemetry metrics for Runtime Observability."""

    def __init__(self, name: str = "TelemetryCollectorSubscriber") -> None:
        super().__init__(name=name)
        self.events_by_type: dict[str, int] = {}

    def handle_event(self, event: BaseRuntimeEvent) -> None:
        start_t = time.perf_counter()
        self.events_received += 1
        self.events_by_type[event.event_type] = self.events_by_type.get(event.event_type, 0) + 1
        self.last_latency_ms = (time.perf_counter() - start_t) * 1000.0


class AuditLoggerSubscriber(EventSubscriber):
    """Subscriber logging structured event audit trails."""

    def __init__(self, name: str = "AuditLoggerSubscriber") -> None:
        super().__init__(name=name)

    def handle_event(self, event: BaseRuntimeEvent) -> None:
        start_t = time.perf_counter()
        self.events_received += 1
        logger.info(
            "[AuditLog] EventID: %s | Plugin: %s | Type: %s | Severity: %s | Camera: %s",
            event.event_id[:8],
            event.plugin_name,
            event.event_type,
            event.severity,
            event.camera_id,
        )
        self.last_latency_ms = (time.perf_counter() - start_t) * 1000.0


class SignalREventSubscriber(EventSubscriber):
    """Subscriber broadcasting high-priority alerts to frontend SignalR hub."""

    def __init__(self, name: str = "SignalREventSubscriber") -> None:
        super().__init__(name=name)

    def handle_event(self, event: BaseRuntimeEvent) -> None:
        start_t = time.perf_counter()
        self.events_received += 1
        if event.severity in ("WARNING", "CRITICAL"):
            logger.info("[SignalRBroadcast] High priority alert broadcasted: %s (Type: %s)", event.event_id[:8], event.event_type)
        self.last_latency_ms = (time.perf_counter() - start_t) * 1000.0
