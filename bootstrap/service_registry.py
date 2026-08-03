"""
Thread-safe Service Registry and Dependency Container for the Engine Bootstrap layer.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Optional, Type, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ServiceNotFoundError(KeyError):
    """Raised when a requested service is not registered in the ServiceRegistry."""


class ServiceRegistry:
    """Thread-safe Service Locator / Dependency Container.

    Allows registering and resolving runtime services (e.g. Logger, EventBus,
    CameraCatalog, OutputProvider, CommunicationManager) without creating tight
    coupling or making the Bootstrap class a God Object.
    """

    def __init__(self) -> None:
        self._services: dict[str, Any] = {}
        self._lock = threading.Lock()

    def register(self, service_name: str, instance: Any) -> None:
        """Register a service instance under a unique string key.

        Args:
            service_name: Unique identifier for the service.
            instance: Service instance object.
        """
        with self._lock:
            if service_name in self._services:
                logger.warning(
                    "ServiceRegistry: Overwriting existing registered service '%s'",
                    service_name,
                )
            self._services[service_name] = instance
            logger.debug("ServiceRegistry: Registered service '%s'", service_name)

    def get(self, service_name: str, default: Optional[T] = None) -> Any | T:
        """Retrieve a registered service instance by name.

        Args:
            service_name: String service identifier.
            default: Fallback value if service is not registered.

        Returns:
            Service instance or default value.
        """
        with self._lock:
            return self._services.get(service_name, default)

    def get_required(self, service_name: str, service_type: Optional[Type[T]] = None) -> T:
        """Retrieve a required registered service instance or raise ServiceNotFoundError.

        Args:
            service_name: String service identifier.
            service_type: Optional type for type checking validation.

        Returns:
            Service instance.

        Raises:
            ServiceNotFoundError: If the service key is not registered.
            TypeError: If registered service does not match requested type.
        """
        with self._lock:
            if service_name not in self._services:
                raise ServiceNotFoundError(
                    f"ServiceRegistry: Required service '{service_name}' is not registered."
                )
            instance = self._services[service_name]

        if service_type is not None and not isinstance(instance, service_type):
            raise TypeError(
                f"ServiceRegistry: Service '{service_name}' expected type {service_type.__name__}, "
                f"but got {type(instance).__name__}."
            )
        return instance  # type: ignore[no-any-return]

    def has(self, service_name: str) -> bool:
        """Check if a service name is currently registered."""
        with self._lock:
            return service_name in self._services

    def unregister(self, service_name: str) -> bool:
        """Unregister a service instance."""
        with self._lock:
            if service_name in self._services:
                del self._services[service_name]
                return True
            return False

    def list_services(self) -> list[str]:
        """List all registered service string identifiers."""
        with self._lock:
            return sorted(list(self._services.keys()))

    def clear(self) -> None:
        """Clear all registered services."""
        with self._lock:
            self._services.clear()
