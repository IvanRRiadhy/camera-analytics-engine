"""
Dynamic Plugin Loader using Python importlib.
"""

from __future__ import annotations

import importlib
import inspect
import logging
from typing import Any, Type, Optional

from camera_analytics.sdk.base_plugin import BaseAnalyticsPlugin

logger = logging.getLogger(__name__)


class PluginLoader:
    """Dynamically loads and instantiates BaseAnalyticsPlugin subclasses using importlib."""

    @staticmethod
    def load_plugin_class(entry_point: str) -> Type[BaseAnalyticsPlugin]:
        """Dynamically import Python entry point string and return BaseAnalyticsPlugin class.

        Args:
            entry_point: Dot-separated Python module or class path (e.g.
               'camera_analytics.plugins.people_counting.plugin.PeopleCountingPlugin' or
               'camera_analytics.plugins.people_counting')

        Returns:
            The resolved BaseAnalyticsPlugin subclass.
        """
        logger.info("[PluginLoader] Dynamically importing entry point '%s'...", entry_point)

        try:
            # Check if entry_point specifies a class directly
            if "." in entry_point:
                module_path, class_name = entry_point.rsplit(".", 1)
                try:
                    mod = importlib.import_module(entry_point)
                    # If entry_point itself is a module, find plugin class in module
                    return PluginLoader._find_plugin_class_in_module(mod)
                except ModuleNotFoundError:
                    # Fallback: import parent module and get class attribute
                    mod = importlib.import_module(module_path)
                    if hasattr(mod, class_name):
                        cls = getattr(mod, class_name)
                        if issubclass(cls, BaseAnalyticsPlugin):
                            return cls
            else:
                mod = importlib.import_module(entry_point)
                return PluginLoader._find_plugin_class_in_module(mod)

        except Exception as exc:
            logger.error("[PluginLoader] Failed to import entry point '%s': %s", entry_point, exc)
            raise RuntimeError(f"Could not load plugin entry point '{entry_point}': {exc}") from exc

        raise RuntimeError(f"No valid BaseAnalyticsPlugin subclass found in entry point '{entry_point}'.")

    @staticmethod
    def _find_plugin_class_in_module(module: Any) -> Type[BaseAnalyticsPlugin]:
        """Scan module attributes for a subclass of BaseAnalyticsPlugin."""
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if inspect.isclass(attr) and issubclass(attr, BaseAnalyticsPlugin) and attr is not BaseAnalyticsPlugin:
                return attr
        raise ValueError(f"Module '{module.__name__}' does not export a BaseAnalyticsPlugin class.")

    @staticmethod
    def instantiate_plugin(entry_point: str, name: str = "", **kwargs: Any) -> BaseAnalyticsPlugin:
        """Instantiate a plugin from its Python entry point string."""
        cls = PluginLoader.load_plugin_class(entry_point)
        instance = cls(name=name or cls.__name__, **kwargs)
        logger.info("[PluginLoader] Successfully instantiated plugin '%s' (%s).", instance.name, cls.__name__)
        return instance
