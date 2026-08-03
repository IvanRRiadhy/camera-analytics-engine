"""
Dynamic Service Plugin Loader.

Imports Python modules dynamically and instantiates `EventService` plugins
with Exception Isolation barriers protecting runtime stability.
"""

from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path
from typing import Optional, Type

from camera_analytics.services.interfaces import EventService
from camera_analytics.services.manifest import ServiceManifest

logger = logging.getLogger(__name__)


class ServiceLoader:
    """Dynamically loads and instantiates EventService plugins."""

    @staticmethod
    def load_service(manifest: ServiceManifest, plugin_dir: Path) -> Optional[EventService]:
        """Import module and instantiate EventService plugin.

        Args:
            manifest: ServiceManifest dataclass.
            plugin_dir: Absolute path to plugin directory.

        Returns:
            Instantiated EventService instance, or None if failed.
        """
        entry_parts = manifest.entry_point.split(":")
        module_name = entry_parts[0]
        class_name = entry_parts[1] if len(entry_parts) > 1 else "ServicePlugin"

        module_path = plugin_dir / f"{module_name}.py"
        if not module_path.exists():
            module_path = plugin_dir / "__init__.py"

        if not module_path.exists():
            logger.error("ServiceLoader: Entry point module '%s' not found in '%s'", module_name, plugin_dir)
            return None

        spec_name = f"camera_analytics.services.plugins.{manifest.service_name}"

        try:
            spec = importlib.util.spec_from_file_location(spec_name, str(module_path))
            if not spec or not spec.loader:
                return None

            mod = importlib.util.module_from_spec(spec)
            sys.modules[spec_name] = mod
            spec.loader.exec_module(mod)

            service_cls: Type[EventService] = getattr(mod, class_name)
            if not issubclass(service_cls, EventService):
                logger.error("ServiceLoader: Class '%s' does not inherit from EventService", class_name)
                return None

            instance = service_cls()
            logger.info("ServiceLoader: Successfully loaded plugin '%s' (%s)", manifest.service_name, class_name)
            return instance

        except Exception as exc:
            logger.error("ServiceLoader: Exception isolation barrier caught load crash in '%s': %s", manifest.service_name, exc)
            return None
