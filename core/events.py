"""
Event bus system.

Provides a publish-subscribe mechanism for decoupled communication
between analytics modules. Modules emit events through the EventBus,
and any registered listener receives them without direct coupling.

This is the backbone of inter-module communication in the framework.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable, Optional

from camera_analytics.models.event import Event, EventCategory

logger = logging.getLogger(__name__)

# Type alias for event handler callbacks
EventHandler = Callable[[Event], None]


@dataclass
class _Subscription:
    """Internal record of a single event subscription.

    Attributes:
        handler: The callback function to invoke.
        subscriber_name: Human-readable name for logging/debugging.
        category_filter: If set, only events of this category are delivered.
        event_type_filter: If set, only events with this exact type are delivered.
    """

    handler: EventHandler
    subscriber_name: str
    category_filter: Optional[EventCategory] = None
    event_type_filter: Optional[str] = None

    def matches(self, event: Event) -> bool:
        """Check if this subscription should receive the given event.

        Args:
            event: The event to test against filters.

        Returns:
            True if the event passes all active filters.
        """
        if self.category_filter is not None:
            if event.category != self.category_filter:
                return False

        if self.event_type_filter is not None:
            if event.event_type != self.event_type_filter:
                return False

        return True


class EventBus:
    """Central publish-subscribe event dispatcher.

    Analytics modules publish Event instances to the bus, and registered
    listeners (handlers) receive matching events. Supports filtering by
    EventCategory and/or specific event_type strings.

    Thread safety is NOT guaranteed — this is designed for single-threaded
    frame-by-frame processing pipelines.

    Example usage::

        bus = EventBus()

        # Subscribe to all ZONE events
        bus.subscribe(
            handler=my_handler,
            subscriber_name="ZoneMonitor",
            category=EventCategory.ZONE,
        )

        # Subscribe to a specific event type
        bus.subscribe(
            handler=alert_handler,
            subscriber_name="AlertSystem",
            event_type="person.entered_restricted",
        )

        # Publish an event — all matching subscribers are notified
        bus.publish(event)
    """

    def __init__(self) -> None:
        self._subscriptions: list[_Subscription] = []
        self._event_log: list[Event] = []
        self._log_enabled: bool = False

    def subscribe(
        self,
        handler: EventHandler,
        subscriber_name: str,
        category: Optional[EventCategory] = None,
        event_type: Optional[str] = None,
    ) -> None:
        """Register a handler to receive events.

        At least one filter (category or event_type) is recommended
        to avoid receiving every event in the system.

        Args:
            handler: Callback function that accepts an Event.
            subscriber_name: Name for logging/debugging purposes.
            category: If set, only deliver events of this category.
            event_type: If set, only deliver events with this exact type string.
        """
        subscription = _Subscription(
            handler=handler,
            subscriber_name=subscriber_name,
            category_filter=category,
            event_type_filter=event_type,
        )
        self._subscriptions.append(subscription)
        logger.debug(
            "Subscribed '%s' (category=%s, event_type=%s)",
            subscriber_name,
            category,
            event_type,
        )

    def unsubscribe(self, subscriber_name: str) -> int:
        """Remove all subscriptions for a given subscriber name.

        Args:
            subscriber_name: Name of the subscriber to remove.

        Returns:
            Number of subscriptions removed.
        """
        before = len(self._subscriptions)
        self._subscriptions = [
            sub
            for sub in self._subscriptions
            if sub.subscriber_name != subscriber_name
        ]
        removed = before - len(self._subscriptions)

        if removed > 0:
            logger.debug(
                "Unsubscribed '%s' (%d subscriptions removed)",
                subscriber_name,
                removed,
            )

        return removed

    def publish(self, event: Event) -> int:
        """Broadcast an event to all matching subscribers.

        Each subscription's filter is checked against the event.
        Matching handlers are invoked synchronously in registration order.

        If a handler raises an exception, it is logged and skipped —
        other handlers still receive the event.

        Args:
            event: The event to broadcast.

        Returns:
            Number of handlers that received the event.
        """
        if self._log_enabled:
            self._event_log.append(event)

        delivered = 0
        for sub in self._subscriptions:
            if sub.matches(event):
                try:
                    sub.handler(event)
                    delivered += 1
                except Exception:
                    logger.exception(
                        "Handler '%s' raised an exception for event '%s'",
                        sub.subscriber_name,
                        event.event_type,
                    )

        logger.debug(
            "Published '%s' [%s] — delivered to %d handler(s)",
            event.event_type,
            event.severity.name,
            delivered,
        )

        return delivered

    def enable_logging(self) -> None:
        """Enable event logging — all published events are stored in memory."""
        self._log_enabled = True

    def disable_logging(self) -> None:
        """Disable event logging."""
        self._log_enabled = False

    def get_event_log(self) -> list[Event]:
        """Retrieve all logged events.

        Returns:
            List of events in chronological order. Empty if logging is disabled.
        """
        return list(self._event_log)

    def clear_event_log(self) -> None:
        """Clear all logged events from memory."""
        self._event_log.clear()

    @property
    def subscriber_count(self) -> int:
        """Total number of active subscriptions."""
        return len(self._subscriptions)

    def clear(self) -> None:
        """Remove all subscriptions and clear the event log."""
        self._subscriptions.clear()
        self._event_log.clear()
        logger.debug("EventBus cleared — all subscriptions removed")
