"""
Module Registry for Human Analytics Subsystem (Sprint H1.5A).

Decouples HumanAnalyticsScheduler from specific AI module implementations,
enabling dynamic module discovery and lifecycle management via BaseHumanAnalyticsModule interfaces.
"""

from __future__ import annotations

import logging
from typing import Optional

from camera_analytics.core.human.base_module import BaseHumanAnalyticsModule

logger = logging.getLogger(__name__)


class ModuleRegistry:
    """Central registry for discovering and accessing BaseHumanAnalyticsModule instances."""

    def __init__(self) -> None:
        self._modules: dict[str, BaseHumanAnalyticsModule] = {}

    def register_module(self, module: BaseHumanAnalyticsModule) -> None:
        """Register a module instance."""
        m_id = module.module_id
        if m_id in self._modules:
            logger.warning("[ModuleRegistry] Overwriting existing registered module '%s'", m_id)
        self._modules[m_id] = module
        logger.info("[ModuleRegistry] Registered module '%s' (Priority: %d)", m_id, module.config.priority)

    def get_module(self, module_id: str) -> Optional[BaseHumanAnalyticsModule]:
        """Retrieve module instance by module_id."""
        return self._modules.get(module_id)

    def list_modules(self) -> list[BaseHumanAnalyticsModule]:
        """List all registered module instances."""
        return list(self._modules.values())

    def unregister_module(self, module_id: str) -> bool:
        """Remove a module from the registry."""
        if module_id in self._modules:
            del self._modules[module_id]
            return True
        return False

    def clear(self) -> None:
        """Clear all registered modules."""
        self._modules.clear()
