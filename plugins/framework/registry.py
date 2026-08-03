"""
Thread-safe Plugin Registry for managing active loaded vision plugins.
"""

from __future__ import annotations

import logging
import threading
from typing import Optional

from camera_analytics.sdk.base_plugin import BaseAnalyticsPlugin

logger = logging.getLogger(__name__)


class PluginRegistry:
    """Registry maintaining active loaded plugins for an AI inference pipeline."""

    def __init__(self) -> None:
        self._plugins: dict[str, BaseAnalyticsPlugin] = {}
        self._lock = threading.RLock()

    def register(self, plugin: BaseAnalyticsPlugin) -> None:
        """Register a loaded plugin instance into the registry."""
        with self._lock:
            self._plugins[plugin.name] = plugin
            logger.info("[PluginRegistry] Registered plugin '%s' (State: %s).", plugin.name, plugin.state.name)

    def unregister(self, name: str) -> Optional[BaseAnalyticsPlugin]:
        """Unregister and remove a plugin by name."""
        with self._lock:
            plugin = self._plugins.pop(name, None)
            if plugin:
                logger.info("[PluginRegistry] Unregistered plugin '%s'.", name)
            return plugin

    def get_plugin(self, name: str) -> Optional[BaseAnalyticsPlugin]:
        """Get a registered plugin instance by name."""
        with self._lock:
            return self._plugins.get(name)

    def get_all_plugins(self) -> list[BaseAnalyticsPlugin]:
        """Get all currently registered plugins."""
        with self._lock:
            return list(self._plugins.values())

    def clear(self) -> None:
        """Clear all registered plugins."""
        with self._lock:
            self._plugins.clear()
