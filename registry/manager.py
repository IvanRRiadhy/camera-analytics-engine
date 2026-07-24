"""
Module Manager Component.

Provides ModuleManager orchestrating Analytics Module lifecycle states, updating ModuleDescriptors,
and supplying priority-ordered active modules to the Analytics Runtime Kernel.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Optional

from camera_analytics.registry.descriptor import ModuleDescriptor, ModuleState
from camera_analytics.registry.store import ModuleRegistry
from camera_analytics.sdk import AnalyticsContext, AnalyticsModule

logger = logging.getLogger(__name__)


class ModuleManager:
    """Manager orchestrating Analytics Module instances, lifecycle state updates, and registry integration."""

    def __init__(self, registry: Optional[ModuleRegistry] = None) -> None:
        self._registry = registry or ModuleRegistry()
        self._lock = threading.Lock()

    @property
    def registry(self) -> ModuleRegistry:
        """Reference to underlying ModuleRegistry store."""
        return self._registry

    def register_module(
        self,
        module: AnalyticsModule,
        descriptor: Optional[ModuleDescriptor] = None,
    ) -> ModuleDescriptor:
        """Register an AnalyticsModule instance into the registry.

        Args:
            module: AnalyticsModule instance.
            descriptor: Optional ModuleDescriptor override.

        Returns:
            Registered ModuleDescriptor.
        """
        return self._registry.register(module, descriptor)

    def unregister_module(self, module_id: str) -> bool:
        """Unregister a module by identifier.

        Args:
            module_id: Module string identifier.

        Returns:
            True if unregistered, False otherwise.
        """
        return self._registry.unregister(module_id)

    def enable_module(self, module_id: str) -> bool:
        """Enable an administrative disabled module.

        Args:
            module_id: Module identifier.

        Returns:
            True if enabled, False otherwise.
        """
        return self._registry.enable(module_id)

    def disable_module(self, module_id: str) -> bool:
        """Disable a module.

        Args:
            module_id: Module identifier.

        Returns:
            True if disabled, False otherwise.
        """
        return self._registry.disable(module_id)

    def set_module_state(self, module_id: str, new_state: ModuleState) -> bool:
        """Update ModuleState enum in ModuleDescriptor.

        Args:
            module_id: Module identifier.
            new_state: Target ModuleState enum.

        Returns:
            True if updated, False if module not found.
        """
        with self._lock:
            desc = self._registry.get_descriptor(module_id)
            if not desc:
                return False

            desc.state = new_state
            logger.debug("ModuleManager: Module '%s' state updated to %s", module_id, new_state.name)
            return True

    def get_active_modules(self) -> list[tuple[ModuleDescriptor, AnalyticsModule]]:
        """Retrieve enabled modules in RUNNING state ordered by priority.

        Returns:
            List of (ModuleDescriptor, AnalyticsModule) tuples.
        """
        enabled_pairs = self._registry.get_enabled()
        return [(desc, mod) for desc, mod in enabled_pairs if desc.state == ModuleState.RUNNING]

    def get_all_descriptors(self) -> list[ModuleDescriptor]:
        """Retrieve all ModuleDescriptors registered in the system.

        Returns:
            List of ModuleDescriptors ordered by priority.
        """
        return [desc for desc, _ in self._registry.get_all()]

    def to_summary(self) -> dict[str, Any]:
        """Generate human-readable summary dictionary of managed modules."""
        all_pairs = self._registry.get_all()
        return {
            "total_registered": len(all_pairs),
            "total_enabled": len(self._registry.get_enabled()),
            "total_running": len(self.get_active_modules()),
            "modules": [desc.to_dict() for desc, _ in all_pairs],
        }
