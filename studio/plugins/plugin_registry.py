"""
Studio PluginRegistry Infrastructure (Sprint H1.5D1.5).

Manages active InspectorPlugin instances and provides manifest validation for future capabilities.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from camera_analytics.studio.plugins.inspector_plugin import IInspectorPanel, InspectorPlugin

logger = logging.getLogger(__name__)


class PluginRegistry:
    """Central registry storing, validating, and ordering active InspectorPlugin extensions."""

    def __init__(self) -> None:
        self._plugins: dict[str, InspectorPlugin] = {}

    def register_plugin(self, plugin: InspectorPlugin) -> bool:
        """Validate manifest and register an InspectorPlugin extension."""
        if not plugin.plugin_id or not plugin.title:
            logger.error(f"[PluginRegistry] Invalid plugin manifest: ID or Title missing!")
            return False

        # Validate dependencies if any
        for dep in plugin.dependencies:
            if dep not in self._plugins:
                logger.warning(f"[PluginRegistry] Plugin '{plugin.plugin_id}' has missing dependency '{dep}'")

        self._plugins[plugin.plugin_id] = plugin
        logger.info(f"[PluginRegistry] Registered Studio Inspector Plugin '{plugin.plugin_id}' v{plugin.version} ({plugin.title})")
        return True

    def get_plugin(self, plugin_id: str) -> Optional[InspectorPlugin]:
        """Retrieve registered plugin by ID."""
        return self._plugins.get(plugin_id)

    def get_all_plugins(self) -> list[InspectorPlugin]:
        """Return list of all registered plugins sorted by priority."""
        return sorted(self._plugins.values(), key=lambda p: p.priority)

    def get_active_panels(self) -> list[IInspectorPanel]:
        """Return instantiated Pure View panels for all registered plugins."""
        return [p.create_panel() for p in self.get_all_plugins()]
