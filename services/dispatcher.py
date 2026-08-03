"""
Decoupled Event Dispatcher Implementation.

Evaluates routing rules, event subscriptions, priorities, and enabled states
to determine target service plugins for incoming events.
"""

from __future__ import annotations

import logging
from typing import Optional

from camera_analytics.communication.models import StandardAnalyticsEvent
from camera_analytics.eventing.models import PlatformEvent
from camera_analytics.services.registry import ServiceRegistry, ServiceRegistryEntry

logger = logging.getLogger(__name__)


class EventDispatcher:
    """Decoupled Event Router evaluating event subscriptions and priorities."""

    def __init__(self, registry: ServiceRegistry) -> None:
        self.registry = registry

    def resolve_target_services(self, event: StandardAnalyticsEvent | PlatformEvent) -> list[ServiceRegistryEntry]:
        """Resolve list of target service entries subscribed to event.

        Args:
            event: StandardAnalyticsEvent or PlatformEvent.

        Returns:
            List of matching ServiceRegistryEntry instances sorted by priority.
        """
        evt_type = event.event_type
        entries = self.registry.list_services()
        matched: list[ServiceRegistryEntry] = []

        for entry in entries:
            manifest = entry.manifest
            if not manifest.enabled:
                continue

            if "*" in manifest.event_types or evt_type in manifest.event_types:
                matched.append(entry)

        # Sort by priority (lower number = higher priority)
        matched.sort(key=lambda e: e.manifest.priority)
        return matched
