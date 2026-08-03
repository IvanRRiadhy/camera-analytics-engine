"""
Event Publisher Plugin Registry.

Provides a controlled registration mechanism for registering and dynamically loading
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

    Allows dynamic plugin registration via `@register_publisher("type")` decorator
    or controlled manifest discovery from camera_analytics.communication.publishers.__all__.
    """

    _registry: dict[str, Type[EventPublisher]] = {}
    _known_classes: dict[str, Type[EventPublisher]] = {}

    @classmethod
    def register(cls, type_name: str) -> Callable[[Type[EventPublisher]], Type[EventPublisher]]:
        """Decorator for registering an EventPublisher subclass under a unique type key."""

        def decorator(publisher_cls: Type[EventPublisher]) -> Type[EventPublisher]:
            clean_type = type_name.strip().lower()
            if clean_type in cls._registry:
                logger.debug(
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
        """Ensure built-in publishers are registered via controlled package manifest imports."""
        if not cls._registry:
            if cls._known_classes:
                cls._registry.update(cls._known_classes)
            else:
                try:
                    # Controlled discovery using explicit publishers manifest
                    import camera_analytics.communication.publishers as pub_manifest
                    for pub_name in getattr(pub_manifest, "__all__", []):
                        pub_cls = getattr(pub_manifest, pub_name, None)
                        if pub_cls is not None and hasattr(pub_cls, "name"):
                            pass  # Decorators register class upon import
                except Exception as exc:
                    logger.debug("PublisherRegistry controlled import error: %s", exc)

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


def register_publisher(type_name: str) -> Callable[[Type[EventPublisher]], Type[EventPublisher]]:
    """Standalone decorator shorthand for PublisherRegistry.register."""
    return PublisherRegistry.register(type_name)
