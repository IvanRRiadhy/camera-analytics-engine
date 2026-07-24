"""
Plugin Loader Models Component.

Provides PluginInstanceRecord and PluginLoadingReport dataclasses representing the status,
descriptors, instantiated modules, and failure breakdowns during dynamic plugin loading.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from camera_analytics.registry.descriptor import ModuleDescriptor
from camera_analytics.sdk import AnalyticsModule


@dataclass(slots=True)
class PluginInstanceRecord:
    """Record representing a dynamically loaded plugin module instance.

    Attributes:
        descriptor: ModuleDescriptor instance configured for the plugin.
        instance: Instantiated AnalyticsModule object (or None if loading failed).
        status: Status string ('LOADED', 'REJECTED', 'IMPORT_ERROR', 'CLASS_NOT_FOUND', 'INVALID_TYPE').
        error_message: Explanatory error details if loading failed.
    """

    descriptor: ModuleDescriptor
    instance: Optional[AnalyticsModule] = None
    status: str = "LOADED"
    error_message: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert record summary to dictionary."""
        return {
            "module_id": self.descriptor.module_id,
            "status": self.status,
            "has_instance": self.instance is not None,
            "error_message": self.error_message,
        }


@dataclass(slots=True)
class PluginLoadingReport:
    """Report summarizing dynamic plugin loading execution results.

    Attributes:
        found_count: Total number of PluginManifests evaluated.
        loaded_records: List of successfully instantiated PluginInstanceRecord objects.
        rejected_records: List of failed PluginInstanceRecord objects.
    """

    found_count: int = 0
    loaded_records: list[PluginInstanceRecord] = field(default_factory=list)
    rejected_records: list[PluginInstanceRecord] = field(default_factory=list)

    @property
    def loaded_count(self) -> int:
        """Number of successfully loaded plugins."""
        return len(self.loaded_records)

    @property
    def rejected_count(self) -> int:
        """Number of rejected plugins."""
        return len(self.rejected_records)

    @property
    def import_error_count(self) -> int:
        """Number of plugins rejected due to ImportError."""
        return sum(1 for r in self.rejected_records if r.status == "IMPORT_ERROR")

    @property
    def class_not_found_count(self) -> int:
        """Number of plugins rejected due to ClassNotFound."""
        return sum(1 for r in self.rejected_records if r.status == "CLASS_NOT_FOUND")

    @property
    def invalid_type_count(self) -> int:
        """Number of plugins rejected due to InvalidType."""
        return sum(1 for r in self.rejected_records if r.status == "INVALID_TYPE")

    def to_dict(self) -> dict[str, Any]:
        """Convert loading report to summary dictionary."""
        return {
            "found_count": self.found_count,
            "loaded_count": self.loaded_count,
            "rejected_count": self.rejected_count,
            "breakdown": {
                "import_error": self.import_error_count,
                "class_not_found": self.class_not_found_count,
                "invalid_type": self.invalid_type_count,
            },
            "loaded_plugins": [r.to_dict() for r in self.loaded_records],
            "rejected_plugins": [r.to_dict() for r in self.rejected_records],
        }
