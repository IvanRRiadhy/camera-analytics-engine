"""
Event Service Base Interface.

Defines the `EventService` Abstract Base Class for platform service plugins.
Service plugins consume `PlatformEvent` or `StandardAnalyticsEvent` objects and can re-emit platform events.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Optional

from camera_analytics.communication.models import StandardAnalyticsEvent
from camera_analytics.eventing.models import PlatformEvent

if TYPE_CHECKING:
    from camera_analytics.services.context import ServiceContext
    from camera_analytics.services.event_bus import PlatformEventBus

logger = logging.getLogger(__name__)


class EventService(ABC):
    """Abstract Base Class for Event-Driven Platform Service Plugins."""

    def __init__(self) -> None:
        self.context: Optional[ServiceContext] = None
        self.event_bus: Optional[Any] = None

    @abstractmethod
    def initialize(self, context: ServiceContext) -> None:
        """Initialize service plugin with lean ServiceContext."""
        self.context = context

    @abstractmethod
    def start(self) -> None:
        """Start service lifecycle execution."""
        pass

    @abstractmethod
    def on_event(self, event: StandardAnalyticsEvent | PlatformEvent) -> None:
        """Process an incoming analytics event or platform event."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stop service execution gracefully."""
        pass

    def dispose(self) -> None:
        """Clean up allocated resources."""
        pass

    def emit_event(self, event: PlatformEvent) -> None:
        """Re-emit a platform event back onto the Platform Event Bus."""
        if self.event_bus:
            self.event_bus.publish(event)
        elif self.context and self.context.get_event_bus():
            self.context.get_event_bus().publish(event)
        else:
            logger.debug("Service '%s' emitted event '%s' (no event bus attached)", self.__class__.__name__, event.event_type)
