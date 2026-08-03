"""
Lean ServiceContext Implementation.

Minimal dependency injection container resolving platform services, storage paths, and loggers
dynamically through `ServiceRegistry` without acting as a God Object.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from camera_analytics.eventing.event_bus import PlatformEventBus
    from camera_analytics.services.registry import ServiceRegistry

logger = logging.getLogger(__name__)


class ServiceContext:
    """Lean Dependency Injection Container for Event Service Plugins."""

    def __init__(
        self,
        service_name: str,
        config: Optional[dict[str, Any]] = None,
        registry: Optional[ServiceRegistry] = None,
        event_bus: Optional[PlatformEventBus] = None,
        storage_dir: Optional[str | Path] = None,
    ) -> None:
        self.service_name = service_name
        self.config = config or {}
        self._registry = registry
        self._event_bus = event_bus
        self.storage_dir = Path(storage_dir or "camera_analytics/storage").resolve()
        self.logger = logging.getLogger(f"services.{service_name}")

    def get_event_bus(self) -> Optional[PlatformEventBus]:
        """Get attached PlatformEventBus."""
        return self._event_bus

    def get_service_dependency(self, service_name: str) -> Optional[Any]:
        """Resolve platform service dynamically through registry DI."""
        if self._registry:
            entry = self._registry.get(service_name)
            return entry.instance if entry else None
        return None
