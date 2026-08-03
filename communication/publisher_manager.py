"""
Publisher Manager & Event Broadcaster.

Coordinates active `EventPublisher` plugins, broadcasts serialized Analytics Events,
monitors publisher health, and enforces Exception Isolation across all publishers.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Optional, Sequence

from camera_analytics.communication.models import StandardAnalyticsEvent
from camera_analytics.communication.publisher_base import EventPublisher
from camera_analytics.communication.registry import PublisherRegistry

logger = logging.getLogger(__name__)


class PublisherManager:
    """Manager responsible for instantiating, running, and broadcasting events to registered EventPublishers.

    Enforces Exception Isolation: A failure or disconnection in one publisher (e.g. MQTT broker down)
    will not interrupt or stop other active publishers (e.g. LogPublisher).
    """

    def __init__(self) -> None:
        self._publishers: dict[str, EventPublisher] = {}
        self._is_initialized = False
        self._is_running = False

    @property
    def publishers(self) -> dict[str, EventPublisher]:
        """Dictionary of loaded EventPublisher instances."""
        return self._publishers

    @property
    def is_running(self) -> bool:
        """Whether the publisher manager is running."""
        return self._is_running

    def register_publisher(self, publisher: EventPublisher) -> None:
        """Register an instantiated EventPublisher directly.

        Args:
            publisher: EventPublisher instance.
        """
        if publisher.name in self._publishers:
            logger.warning("PublisherManager: Overwriting registered publisher '%s'", publisher.name)
        self._publishers[publisher.name] = publisher
        logger.info("PublisherManager: Registered active publisher '%s'", publisher.name)

    def load_from_config(self, configs: Sequence[dict[str, Any]]) -> None:
        """Instantiate and load publishers from configuration list using PublisherRegistry.

        Args:
            configs: List of publisher config dicts (e.g. `[{'type': 'log', 'enabled': True, ...}]`).
        """
        for cfg in configs:
            pub_type = cfg.get("type")
            enabled = cfg.get("enabled", True)
            if not pub_type or not enabled:
                continue

            pub_name = cfg.get("name", pub_type)
            try:
                publisher = PublisherRegistry.create(type_name=pub_type, name=pub_name, enabled=enabled)
                publisher.initialize(cfg)
                self.register_publisher(publisher)
            except Exception as exc:
                logger.error("PublisherManager: Failed to load publisher '%s' of type '%s' (%s)",
                             pub_name, pub_type, exc)

    def get_health_status(self) -> dict[str, dict[str, Any]]:
        """Get health status snapshot for all registered publishers."""
        return {name: pub.get_health() for name, pub in self._publishers.items()}

    # --- Lifecycle Contracts ---

    def initialize(self, global_config: Optional[dict[str, Any]] = None) -> None:
        """Initialize all registered publishers."""
        if self._is_initialized:
            return

        for name, pub in list(self._publishers.items()):
            try:
                pub.initialize(global_config or {})
            except Exception as exc:
                logger.error("Exception Isolation: Failed to initialize publisher '%s' (%s)", name, exc)

        self._is_initialized = True

    def start(self) -> None:
        """Start all initialized publishers."""
        if self._is_running:
            return

        for name, pub in list(self._publishers.items()):
            if pub.is_enabled:
                try:
                    if not pub.is_initialized:
                        pub.initialize({})
                    pub.start()
                except Exception as exc:
                    logger.error("Exception Isolation: Failed to start publisher '%s' (%s)", name, exc)

        self._is_running = True
        logger.info("PublisherManager: Started %d publisher(s)", len(self._publishers))

    def broadcast(
        self,
        event: StandardAnalyticsEvent,
        serialized_payload: str,
        target_publishers: Optional[list[str]] = None,
    ) -> tuple[int, int]:
        """Broadcast serialized event payload to active target publishers with Exception Isolation.

        Args:
            event: StandardAnalyticsEvent instance.
            serialized_payload: Pre-serialized JSON string.
            target_publishers: Optional list of target publisher names to publish to.

        Returns:
            Tuple of (successful_publishes_count, failed_publishes_count).
        """
        success_count = 0
        failure_count = 0

        for name, pub in self._publishers.items():
            if target_publishers is not None and name not in target_publishers:
                continue

            if not pub.is_running or not pub.is_enabled:
                continue

            try:
                ok = pub.publish(event, serialized_payload)
                if ok:
                    success_count += 1
                else:
                    failure_count += 1
            except Exception as exc:
                failure_count += 1
                logger.exception("Exception Isolation: Publisher '%s' exception during publish", name)

        return success_count, failure_count

    def flush(self) -> None:
        """Flush buffers across all active publishers."""
        for name, pub in self._publishers.items():
            if pub.is_running:
                try:
                    pub.flush()
                except Exception as exc:
                    logger.error("Exception Isolation: Failed to flush publisher '%s' (%s)", name, exc)

    def stop(self) -> None:
        """Stop all active publishers."""
        for name, pub in list(self._publishers.items()):
            try:
                pub.stop()
            except Exception as exc:
                logger.error("Exception Isolation: Failed to stop publisher '%s' (%s)", name, exc)

        self._is_running = False

    def dispose(self) -> None:
        """Dispose all registered publishers."""
        if self._is_running:
            self.stop()

        for name, pub in list(self._publishers.items()):
            try:
                pub.dispose()
            except Exception as exc:
                logger.error("Exception Isolation: Failed to dispose publisher '%s' (%s)", name, exc)

        self._publishers.clear()
        self._is_initialized = False
