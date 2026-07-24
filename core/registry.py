"""
Module registry.

Manages the collection of registered analytics modules. Provides
registration, unregistration, lookup, and dependency validation.
The Pipeline uses the Registry to manage its module lifecycle.
"""

from __future__ import annotations

import logging
from typing import Optional

from camera_analytics.core.base_module import AnalyticsModule, ModuleLifecycle

logger = logging.getLogger(__name__)


class RegistryError(Exception):
    """Raised when a registry operation fails."""


class ModuleRegistry:
    """Registry that manages analytics module instances.

    Handles registration, unregistration, ordered retrieval,
    and dependency validation for all analytics modules in a pipeline.

    Each module is keyed by its unique name (from module_info.name).
    Duplicate names are not allowed.

    Example usage::

        registry = ModuleRegistry()
        registry.register(PeopleAnalytics())
        registry.register(PPEAnalytics())

        for module in registry.get_all():
            module.initialize(config, event_bus)

        # Later...
        registry.unregister("people_analytics")
    """

    def __init__(self) -> None:
        self._modules: dict[str, AnalyticsModule] = {}
        self._registration_order: list[str] = []

    def register(self, module: AnalyticsModule) -> None:
        """Register an analytics module.

        Args:
            module: The module instance to register.

        Raises:
            RegistryError: If a module with the same name is already registered.
            RegistryError: If the module is not in CREATED state.
        """
        name = module.name

        if name in self._modules:
            raise RegistryError(
                f"Module '{name}' is already registered. "
                f"Unregister it first before re-registering."
            )

        if module.lifecycle != ModuleLifecycle.CREATED:
            raise RegistryError(
                f"Module '{name}' must be in CREATED state to register "
                f"(current state: {module.lifecycle.name})."
            )

        self._modules[name] = module
        self._registration_order.append(name)

        logger.info(
            "Registered module '%s' v%s",
            name,
            module.module_info.version,
        )

    def unregister(self, module_name: str) -> Optional[AnalyticsModule]:
        """Unregister a module by name.

        The module is removed from the registry. If it is still running,
        the caller is responsible for shutting it down first.

        Args:
            module_name: Name of the module to remove.

        Returns:
            The removed module instance, or None if not found.
        """
        module = self._modules.pop(module_name, None)

        if module is not None:
            self._registration_order.remove(module_name)
            logger.info("Unregistered module '%s'", module_name)
        else:
            logger.warning(
                "Attempted to unregister unknown module '%s'", module_name
            )

        return module

    def get(self, module_name: str) -> Optional[AnalyticsModule]:
        """Look up a module by name.

        Args:
            module_name: Name of the module to find.

        Returns:
            The module instance, or None if not found.
        """
        return self._modules.get(module_name)

    def get_required(self, module_name: str) -> AnalyticsModule:
        """Look up a module by name, raising if not found.

        Args:
            module_name: Name of the module to find.

        Returns:
            The module instance.

        Raises:
            RegistryError: If the module is not registered.
        """
        module = self._modules.get(module_name)
        if module is None:
            raise RegistryError(
                f"Required module '{module_name}' is not registered."
            )
        return module

    def get_all(self) -> list[AnalyticsModule]:
        """Get all registered modules in registration order.

        Returns:
            List of module instances in the order they were registered.
        """
        return [self._modules[name] for name in self._registration_order]

    def get_enabled(self) -> list[AnalyticsModule]:
        """Get all modules that are ready or running.

        Returns:
            List of modules in READY or RUNNING state,
            in registration order.
        """
        return [
            self._modules[name]
            for name in self._registration_order
            if self._modules[name].is_ready
        ]

    def has(self, module_name: str) -> bool:
        """Check if a module is registered.

        Args:
            module_name: Name to check.

        Returns:
            True if the module is registered.
        """
        return module_name in self._modules

    def validate_dependencies(self) -> list[str]:
        """Validate that all module dependencies are satisfied.

        Checks each module's declared dependencies against the
        set of registered module names.

        Returns:
            List of error messages. Empty list means all dependencies
            are satisfied.
        """
        errors: list[str] = []

        for name in self._registration_order:
            module = self._modules[name]
            for dep in module.module_info.dependencies:
                if dep not in self._modules:
                    errors.append(
                        f"Module '{name}' requires '{dep}', "
                        f"but it is not registered."
                    )

        if errors:
            for error in errors:
                logger.error("Dependency error: %s", error)
        else:
            logger.debug("All module dependencies satisfied")

        return errors

    @property
    def count(self) -> int:
        """Number of registered modules."""
        return len(self._modules)

    @property
    def module_names(self) -> list[str]:
        """List of registered module names in registration order."""
        return list(self._registration_order)

    def clear(self) -> None:
        """Remove all registered modules.

        Does NOT call shutdown() on modules — the caller is responsible
        for proper lifecycle management before clearing.
        """
        self._modules.clear()
        self._registration_order.clear()
        logger.debug("Registry cleared — all modules removed")

    def __repr__(self) -> str:
        return (
            f"ModuleRegistry(modules={self._registration_order})"
        )
