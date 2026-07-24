"""
Event Publisher Base Contract.

Defines the abstract base class `EventPublisher` with full lifecycle contracts
for external communication publishers (Log, MQTT, WebSocket, Kafka, RabbitMQ, etc.).
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Optional

from camera_analytics.communication.models import StandardAnalyticsEvent

logger = logging.getLogger(__name__)


class EventPublisher(ABC):
    """Abstract Base Class for all external communication publishers in the platform.

    Provides standard lifecycle management (initialize, start, publish, flush, stop, dispose)
    and health status monitoring.

    Attributes:
        name: String identifier of the publisher instance.
        enabled: Whether this publisher is enabled.
    """

    def __init__(self, name: str, enabled: bool = True) -> None:
        self._name = name
        self._enabled = enabled
        self._is_initialized = False
        self._is_running = False
        self._is_healthy = True

    @property
    def name(self) -> str:
        """Publisher identifier name."""
        return self._name

    @property
    def is_enabled(self) -> bool:
        """Whether the publisher is enabled in configuration."""
        return self._enabled

    @property
    def is_initialized(self) -> bool:
        """Whether the publisher has been initialized."""
        return self._is_initialized

    @property
    def is_running(self) -> bool:
        """Whether the publisher is actively running."""
        return self._is_running

    @property
    def is_healthy(self) -> bool:
        """Whether the publisher connection is healthy."""
        return self._is_healthy

    # --- Lifecycle Contracts ---

    def initialize(self, config: dict[str, Any]) -> None:
        """Initialize publisher with configuration dictionary."""
        if self._is_initialized:
            return
        self.on_initialize(config)
        self._is_initialized = True
        logger.debug("EventPublisher '%s' initialized", self._name)

    def start(self) -> None:
        """Start the publisher background client or file stream."""
        if not self._is_initialized:
            raise RuntimeError(f"Cannot start EventPublisher '{self._name}': not initialized.")
        if self._is_running or not self._enabled:
            return
        self.on_start()
        self._is_running = True
        self._is_healthy = True
        logger.debug("EventPublisher '%s' started", self._name)

    @abstractmethod
    def publish(self, event: StandardAnalyticsEvent, serialized_payload: str) -> bool:
        """Publish a serialized Analytics Event payload to external transport target.

        Args:
            event: StandardAnalyticsEvent dataclass instance.
            serialized_payload: Pre-serialized JSON payload string.

        Returns:
            True if published successfully, False otherwise.
        """
        pass

    def flush(self) -> None:
        """Flush pending buffered messages or file buffers to disk/network."""
        if self._is_running:
            self.on_flush()

    def stop(self) -> None:
        """Stop the publisher client cleanly."""
        if not self._is_running:
            return
        self.flush()
        self.on_stop()
        self._is_running = False
        logger.debug("EventPublisher '%s' stopped", self._name)

    def dispose(self) -> None:
        """Dispose and release allocated publisher resources."""
        if self._is_running:
            self.stop()
        self.on_dispose()
        self._is_initialized = False
        logger.debug("EventPublisher '%s' disposed", self._name)

    # --- Overridable Hooks ---

    def on_initialize(self, config: dict[str, Any]) -> None:
        """Hook called during initialization."""
        pass

    def on_start(self) -> None:
        """Hook called when starting publisher."""
        pass

    def on_flush(self) -> None:
        """Hook called when flushing buffers."""
        pass

    def on_stop(self) -> None:
        """Hook called when stopping publisher."""
        pass

    def on_dispose(self) -> None:
        """Hook called when disposing publisher."""
        pass
