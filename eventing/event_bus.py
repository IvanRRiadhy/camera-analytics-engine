"""
Central Platform Event Bus Implementation.

High-performance pub-sub event distribution hub shared across all platform runtimes.
"""

from __future__ import annotations

import logging
import threading
from typing import Callable, Optional

from camera_analytics.eventing.models import PlatformEvent

logger = logging.getLogger(__name__)

EventCallback = Callable[[PlatformEvent], None]


class PlatformEventBus:
    """Thread-safe central pub-sub Event Bus for PlatformEvent distribution."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[EventCallback]] = {}
        self._global_subscribers: list[EventCallback] = []
        self._lock = threading.Lock()

    def subscribe(self, event_type: str, callback: EventCallback) -> None:
        """Subscribe a callback to a specific event_type or '*' for all events."""
        with self._lock:
            if event_type == "*":
                if callback not in self._global_subscribers:
                    self._global_subscribers.append(callback)
            else:
                if event_type not in self._subscribers:
                    self._subscribers[event_type] = []
                if callback not in self._subscribers[event_type]:
                    self._subscribers[event_type].append(callback)
        logger.debug("PlatformEventBus subscribed callback to event_type '%s'", event_type)

    def publish(self, event: PlatformEvent) -> int:
        """Publish a PlatformEvent to all subscribed callbacks.

        Args:
            event: Immutable PlatformEvent instance.

        Returns:
            Number of callbacks notified.
        """
        with self._lock:
            type_callbacks = list(self._subscribers.get(event.event_type, []))
            global_callbacks = list(self._global_subscribers)

        all_callbacks = type_callbacks + global_callbacks
        notified = 0

        for cb in all_callbacks:
            try:
                cb(event)
                notified += 1
            except Exception as exc:
                logger.error("PlatformEventBus exception in subscriber callback for '%s': %s", event.event_type, exc)

        return notified
