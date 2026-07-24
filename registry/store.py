"""
Module Registry Store Component.

Provides ModuleRegistry store managing registration, enabling/disabling, priority ordering,
and querying of Analytics Modules and their ModuleDescriptors.
"""

from __future__ import annotations

import logging
import threading
from typing import Optional, Sequence

from camera_analytics.registry.descriptor import ModuleDescriptor, ModuleState
from camera_analytics.sdk import AnalyticsModule

logger = logging.getLogger(__name__)


class ModuleRegistry:
    """Central store managing registration, descriptors, priority ordering, and lifecycle states of Analytics Modules."""

    def __init__(self) -> None:
        self._descriptors: dict[str, ModuleDescriptor] = {}
        self._modules: dict[str, AnalyticsModule] = {}
        self._lock = threading.Lock()

    def register(self, module: AnalyticsModule, descriptor: Optional[ModuleDescriptor] = None) -> ModuleDescriptor:
        """Register an AnalyticsModule instance into the registry store.

        Args:
            module: AnalyticsModule instance.
            descriptor: Optional custom ModuleDescriptor. If None, default descriptor is constructed.

        Returns:
            Registered ModuleDescriptor instance.
        """
        with self._lock:
            if isinstance(module, ModuleDescriptor):
                descriptor = module
                module_id = descriptor.module_id
                self._descriptors[module_id] = descriptor
                logger.info("ModuleRegistry: Registered descriptor '%s' (priority=%d)", module_id, descriptor.priority)
                return descriptor

            module_id = module.name

            if descriptor is None:
                descriptor = ModuleDescriptor(
                    module_id=module_id,
                    module_name=module.name,
                    description=getattr(module, "description", "Analytics Module"),
                    priority=getattr(module, "priority", 100),
                    state=ModuleState.REGISTERED,
                )

            descriptor.state = ModuleState.REGISTERED
            self._descriptors[module_id] = descriptor
            self._modules[module_id] = module

            logger.info("ModuleRegistry: Registered module '%s' (priority=%d)", module_id, descriptor.priority)
            return descriptor

    def register_descriptor(self, descriptor: ModuleDescriptor) -> ModuleDescriptor:
        """Register a ModuleDescriptor directly without instantiation.

        Args:
            descriptor: ModuleDescriptor instance.

        Returns:
            Registered ModuleDescriptor.
        """
        with self._lock:
            descriptor.state = ModuleState.REGISTERED
            self._descriptors[descriptor.module_id] = descriptor
            logger.info("ModuleRegistry: Registered descriptor '%s' (priority=%d)", descriptor.module_id, descriptor.priority)
            return descriptor

    def unregister(self, module_id: str) -> bool:
        """Unregister a module by its module_id.

        Args:
            module_id: Unique string identifier.

        Returns:
            True if unregistered successfully, False if module_id not found.
        """
        with self._lock:
            if module_id not in self._descriptors:
                return False

            desc = self._descriptors.pop(module_id)
            desc.state = ModuleState.DISPOSED
            self._modules.pop(module_id, None)

            logger.info("ModuleRegistry: Unregistered module '%s'", module_id)
            return True

    def enable(self, module_id: str) -> bool:
        """Enable an administrative disabled module.

        Args:
            module_id: Module identifier.

        Returns:
            True if enabled successfully, False if not found.
        """
        with self._lock:
            desc = self._descriptors.get(module_id)
            if not desc:
                return False

            desc.enabled = True
            logger.info("ModuleRegistry: Enabled module '%s'", module_id)
            return True

    def disable(self, module_id: str) -> bool:
        """Disable an administrative enabled module.

        Args:
            module_id: Module identifier.

        Returns:
            True if disabled successfully, False if not found.
        """
        with self._lock:
            desc = self._descriptors.get(module_id)
            if not desc:
                return False

            desc.enabled = False
            desc.state = ModuleState.DISABLED
            logger.info("ModuleRegistry: Disabled module '%s'", module_id)
            return True

    def get(self, module_id: str) -> Optional[AnalyticsModule]:
        """Retrieve AnalyticsModule instance by module_id.

        Args:
            module_id: Module identifier.

        Returns:
            AnalyticsModule instance or None.
        """
        with self._lock:
            return self._modules.get(module_id)

    def get_descriptor(self, module_id: str) -> Optional[ModuleDescriptor]:
        """Retrieve ModuleDescriptor by module_id.

        Args:
            module_id: Module identifier.

        Returns:
            ModuleDescriptor instance or None.
        """
        with self._lock:
            return self._descriptors.get(module_id)

    def get_all_descriptors(self) -> list[ModuleDescriptor]:
        """Retrieve all registered ModuleDescriptors ordered by priority ascending.

        Returns:
            List of ModuleDescriptor instances sorted by priority.
        """
        with self._lock:
            descriptors = list(self._descriptors.values())
            descriptors.sort(key=lambda d: d.priority)
            return descriptors

    def get_all(self) -> list[tuple[ModuleDescriptor, AnalyticsModule]]:
        """Retrieve all registered (descriptor, module) pairs ordered by priority ascending.

        Returns:
            List of (ModuleDescriptor, AnalyticsModule) tuples sorted by priority.
        """
        with self._lock:
            pairs = [(desc, self._modules[mid]) for mid, desc in self._descriptors.items() if mid in self._modules]
            pairs.sort(key=lambda item: item[0].priority)
            return pairs

    def get_enabled(self) -> list[tuple[ModuleDescriptor, AnalyticsModule]]:
        """Retrieve all enabled (descriptor, module) pairs ordered by priority ascending.

        Returns:
            List of enabled (ModuleDescriptor, AnalyticsModule) tuples sorted by priority.
        """
        with self._lock:
            pairs = [
                (desc, self._modules[mid])
                for mid, desc in self._descriptors.items()
                if desc.enabled and mid in self._modules
            ]
            pairs.sort(key=lambda item: item[0].priority)
            return pairs
