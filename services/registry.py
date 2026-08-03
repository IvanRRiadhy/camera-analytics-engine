"""
Service Registry Subsystem Implementation.

Central registry tracking service instances, manifests, health states, and lifecycle states.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Optional

from camera_analytics.services.interfaces import EventService
from camera_analytics.services.lifecycle import ServiceLifecycleState
from camera_analytics.services.manifest import ServiceManifest

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ServiceRegistryEntry:
    """Registry Entry holding instance, manifest, and lifecycle state."""

    manifest: ServiceManifest
    instance: EventService
    state: ServiceLifecycleState = ServiceLifecycleState.UNINITIALIZED
    error_count: int = 0
    last_error: Optional[str] = None


class ServiceRegistry:
    """Thread-safe central registry for Event Services."""

    def __init__(self) -> None:
        self._entries: dict[str, ServiceRegistryEntry] = {}
        self._capability_index: dict[str, str] = {}
        self._lock = threading.Lock()

    def register(self, manifest: ServiceManifest, instance: EventService) -> None:
        """Register a service instance with its manifest."""
        with self._lock:
            self._entries[manifest.service_name] = ServiceRegistryEntry(
                manifest=manifest,
                instance=instance,
                state=ServiceLifecycleState.INITIALIZED,
            )
            for cap in manifest.capabilities:
                self._capability_index[cap] = manifest.service_name
        logger.debug("ServiceRegistry registered service '%s'", manifest.service_name)

    def unregister(self, service_name: str) -> None:
        """Unregister a service by name."""
        with self._lock:
            entry = self._entries.pop(service_name, None)
            if entry:
                for cap in entry.manifest.capabilities:
                    self._capability_index.pop(cap, None)

    def get(self, service_name: str) -> Optional[ServiceRegistryEntry]:
        """Get registry entry by service name."""
        with self._lock:
            return self._entries.get(service_name)

    def get_by_capability(self, capability: str) -> Optional[ServiceRegistryEntry]:
        """Get registry entry providing capability."""
        with self._lock:
            s_name = self._capability_index.get(capability)
            return self._entries.get(s_name) if s_name else None

    def list_services(self) -> list[ServiceRegistryEntry]:
        """List all registered service entries."""
        with self._lock:
            return list(self._entries.values())
