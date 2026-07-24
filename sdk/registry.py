"""
Analytics Plugin Registry.

Provides a decoupled plugin registration mechanism for registering and dynamically loading
Analytics Modules by string identifier without modifying core framework code.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable, Type

if TYPE_CHECKING:
    from camera_analytics.sdk.module import AnalyticsModule

logger = logging.getLogger(__name__)


class AnalyticsRegistry:
    """Central registry for Analytics Module plugins.

    Allows dynamic plugin registration via method call or `@register_analytics("name")` decorator.
    Zero hardcoded analytics references.
    """

    _registry: dict[str, Type[AnalyticsModule]] = {}

    @classmethod
    def register(cls, name: str) -> Callable[[Type[AnalyticsModule]], Type[AnalyticsModule]]:
        """Decorator for registering an AnalyticsModule subclass under a unique name key.

        Usage::

            @AnalyticsRegistry.register("people_counter")
            class PeopleCounter(AnalyticsModule):
                ...

        Args:
            name: Unique string identifier for the analytics plugin.

        Returns:
            Decorator function.
        """

        def decorator(module_cls: Type[AnalyticsModule]) -> Type[AnalyticsModule]:
            clean_name = name.strip().lower()
            if clean_name in cls._registry:
                logger.warning(
                    "AnalyticsRegistry: Overwriting existing module registration for '%s'", clean_name
                )
            cls._registry[clean_name] = module_cls
            logger.debug("AnalyticsRegistry: Registered module '%s' -> %s", clean_name, module_cls.__name__)
            return module_cls

        return decorator

    @classmethod
    def get(cls, name: str) -> Optional[Type[AnalyticsModule]]:
        """Retrieve registered AnalyticsModule class by string key.

        Args:
            name: String identifier of the module.

        Returns:
            Registered AnalyticsModule class, or None if not found.
        """
        clean_name = name.strip().lower()
        return cls._registry.get(clean_name)

    @classmethod
    def create(cls, name: str, **kwargs: Any) -> AnalyticsModule:
        """Instantiate a registered AnalyticsModule by name.

        Args:
            name: String identifier of the module.
            **kwargs: Additional keyword arguments passed to module constructor.

        Returns:
            Instantiated AnalyticsModule instance.

        Raises:
            KeyError: If no module is registered under the given name.
        """
        clean_name = name.strip().lower()
        module_cls = cls.get(clean_name)
        if module_cls is None:
            available = ", ".join(f"'{k}'" for k in cls._registry.keys())
            raise KeyError(
                f"AnalyticsRegistry: Unknown module '{name}'. Available registered modules: [{available}]"
            )
        if "name" not in kwargs:
            kwargs["name"] = clean_name
        return module_cls(**kwargs)

    @classmethod
    def list_registered(cls) -> list[str]:
        """List all registered module string identifiers."""
        return sorted(list(cls._registry.keys()))

    @classmethod
    def is_registered(cls, name: str) -> bool:
        """Check if a module is registered by name."""
        return name.strip().lower() in cls._registry

    @classmethod
    def clear(cls) -> None:
        """Clear all registered modules (used in testing)."""
        cls._registry.clear()


def register_analytics(name: str) -> Callable[[Type[AnalyticsModule]], Type[AnalyticsModule]]:
    """Helper shortcut decorator for registering an AnalyticsModule plugin."""
    return AnalyticsRegistry.register(name)
