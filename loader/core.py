"""
Plugin Loader Core Component.

Provides PluginLoader class performing dynamic import, reflection, type checking,
and instantiation of AnalyticsModule classes specified by PluginManifest entry points.
"""

from __future__ import annotations

import importlib
import logging
from typing import Optional, Sequence, Type

from camera_analytics.discovery.manifest import PluginManifest
from camera_analytics.loader.models import PluginInstanceRecord, PluginLoadingReport
from camera_analytics.registry.descriptor import ModuleDescriptor
from camera_analytics.sdk import AnalyticsModule

logger = logging.getLogger(__name__)


class PluginLoader:
    """Loader performing dynamic import, reflection, type checking, and instantiation of Analytics Modules."""

    def __init__(self) -> None:
        pass

    def load(self, manifest: PluginManifest) -> PluginInstanceRecord:
        """Dynamically import, reflect, validate, and instantiate an AnalyticsModule from a PluginManifest.

        Args:
            manifest: PluginManifest instance describing the module entry_point.

        Returns:
            PluginInstanceRecord containing descriptor, instance, and status.
        """
        descriptor = manifest.to_descriptor()
        entry_point = manifest.entry_point.strip()

        # 1. Parse module path and class name from entry_point (e.g. 'pkg.module.MyClass')
        if "." not in entry_point:
            err_msg = f"Invalid entry_point format '{entry_point}'. Expected 'module.path.ClassName'"
            logger.warning("PluginLoader: %s for plugin '%s'", err_msg, manifest.plugin_id)
            return PluginInstanceRecord(descriptor=descriptor, status="IMPORT_ERROR", error_message=err_msg)

        module_path, class_name = entry_point.rsplit(".", 1)

        # 2. Dynamic Import using importlib
        try:
            py_module = importlib.import_module(module_path)
        except ImportError as exc:
            err_msg = f"Failed to import Python module '{module_path}': {exc}"
            logger.warning("PluginLoader: %s for plugin '%s'", err_msg, manifest.plugin_id)
            return PluginInstanceRecord(descriptor=descriptor, status="IMPORT_ERROR", error_message=err_msg)
        except Exception as exc:
            err_msg = f"Unexpected error during import of '{module_path}': {exc}"
            logger.error("PluginLoader: %s for plugin '%s'", err_msg, manifest.plugin_id)
            return PluginInstanceRecord(descriptor=descriptor, status="IMPORT_ERROR", error_message=err_msg)

        # 3. Reflection: Extract class symbol from imported python module
        try:
            target_cls: Type[Any] = getattr(py_module, class_name)
        except AttributeError:
            err_msg = f"Class '{class_name}' not found in imported module '{module_path}'"
            logger.warning("PluginLoader: %s for plugin '%s'", err_msg, manifest.plugin_id)
            return PluginInstanceRecord(descriptor=descriptor, status="CLASS_NOT_FOUND", error_message=err_msg)

        # 4. Type Validation: Ensure class inherits from AnalyticsModule
        if not isinstance(target_cls, type) or not issubclass(target_cls, AnalyticsModule):
            err_msg = f"Class '{class_name}' in '{module_path}' does not inherit from AnalyticsModule"
            logger.warning("PluginLoader: %s for plugin '%s'", err_msg, manifest.plugin_id)
            return PluginInstanceRecord(descriptor=descriptor, status="INVALID_TYPE", error_message=err_msg)

        # 5. Dynamic Instantiation
        try:
            # Instantiate with name=manifest.plugin_id if signature accepts name
            try:
                instance = target_cls(name=manifest.plugin_id)
            except TypeError:
                # Fallback to no-argument constructor if name keyword is not required
                instance = target_cls()
                if hasattr(instance, "name") and not instance.name:
                    instance.name = manifest.plugin_id

            logger.info("PluginLoader: Successfully instantiated AnalyticsModule '%s' (%s)", manifest.plugin_id, class_name)
            return PluginInstanceRecord(descriptor=descriptor, instance=instance, status="LOADED")

        except Exception as exc:
            err_msg = f"Error instantiating class '{class_name}': {exc}"
            logger.error("PluginLoader: %s for plugin '%s'", err_msg, manifest.plugin_id)
            return PluginInstanceRecord(descriptor=descriptor, status="REJECTED", error_message=err_msg)

    def load_all(self, manifests: Sequence[PluginManifest]) -> PluginLoadingReport:
        """Dynamically load and instantiate multiple PluginManifest instances.

        Args:
            manifests: Sequence of PluginManifest objects.

        Returns:
            PluginLoadingReport summarizing loaded vs rejected records.
        """
        report = PluginLoadingReport(found_count=len(manifests))

        for manifest in manifests:
            record = self.load(manifest)
            if record.status == "LOADED" and record.instance is not None:
                report.loaded_records.append(record)
            else:
                report.rejected_records.append(record)

        logger.info(
            "PluginLoader: Dynamic Loading Complete (Loaded: %d, Rejected: %d)",
            report.loaded_count,
            report.rejected_count,
        )
        return report
