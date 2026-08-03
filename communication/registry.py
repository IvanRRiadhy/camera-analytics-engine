"""
Event Publisher Plugin Registry.

Provides a decoupled plugin registration mechanism for registering and dynamically loading
EventPublisher plugins by string identifier without modifying Communication Layer core.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable, Optional, Type

if TYPE_CHECKING:
    from camera_analytics.communication.publisher_base import EventPublisher

logger = logging.getLogger(__name__)


class PublisherRegistry:
    """Central plugin registry for EventPublisher plugins.

    Allows dynamic plugin registration via method call or `@register_publisher("type")` decorator.
    Zero hardcoded publisher references.
    """

    _registry: dict[str, Type[EventPublisher]] = {}
    _known_classes: dict[str, Type[EventPublisher]] = {}

    @classmethod
    def register(cls, type_name: str) -> Callable[[Type[EventPublisher]], Type[EventPublisher]]:
        """Decorator for registering an EventPublisher subclass under a unique type key."""

        def decorator(publisher_cls: Type[EventPublisher]) -> Type[EventPublisher]:
            clean_type = type_name.strip().lower()
            if clean_type in cls._registry:
                logger.warning(
                    "PublisherRegistry: Overwriting existing publisher registration for '%s'", clean_type
                )
            cls._registry[clean_type] = publisher_cls
            cls._known_classes[clean_type] = publisher_cls
            logger.debug(
                "PublisherRegistry: Registered publisher '%s' -> %s", clean_type, publisher_cls.__name__
            )
            return publisher_cls

        return decorator

    @classmethod
    def _ensure_defaults(cls) -> None:
        """Ensure built-in publishers are registered if registry is empty."""
        if not cls._registry:
            if cls._known_classes:
                cls._registry.update(cls._known_classes)
            else:
                try:
                    import camera_analytics.communication.publishers.console_publisher  # noqa: F401
                    import camera_analytics.communication.publishers.log_publisher      # noqa: F401
                    import camera_analytics.communication.publishers.mqtt_publisher     # noqa: F401
                    import camera_analytics.communication.publishers.rabbitmq_publisher # noqa: F401
                    import camera_analytics.communication.publishers.rest_publisher     # noqa: F401
                except Exception as exc:
                    logger.debug("PublisherRegistry auto-import error: %s", exc)

    @classmethod
    def get(cls, type_name: str) -> Optional[Type[EventPublisher]]:
        """Retrieve registered EventPublisher class by string key."""
        cls._ensure_defaults()
        clean_type = type_name.strip().lower()
        return cls._registry.get(clean_type)

    @classmethod
    def create(cls, type_name: str, name: Optional[str] = None, **kwargs: Any) -> EventPublisher:
        """Instantiate a registered EventPublisher by type name."""
        clean_type = type_name.strip().lower()
        publisher_cls = cls.get(clean_type)
        if publisher_cls is None:
            available = ", ".join(f"'{k}'" for k in cls._registry.keys())
            raise KeyError(
                f"PublisherRegistry: Unknown publisher type '{type_name}'. Available registered types: [{available}]"
            )

        instance_name = name if name is not None else clean_type
        if "name" not in kwargs:
            kwargs["name"] = instance_name

        return publisher_cls(**kwargs)

    @classmethod
    def list_registered(cls) -> list[str]:
        """List all registered publisher type string identifiers."""
        cls._ensure_defaults()
        return sorted(list(cls._registry.keys()))

    @classmethod
    def is_registered(cls, type_name: str) -> bool:
        """Check if a publisher type is registered."""
        cls._ensure_defaults()
        return type_name.strip().lower() in cls._registry

    @classmethod
    def clear(cls) -> None:
        """Clear all registered publishers (used in testing)."""
        cls._registry.clear()


def register_publisher(type_name: str) -> Callable[[Type[EventPublisher]], Type[EventPublisher]]:
    """Helper shortcut decorator for registering an EventPublisher plugin."""
    return PublisherRegistry.register(type_name)
