"""
Plugin Manifest Component.

Provides PluginManifest immutable dataclass representing descriptive plugin metadata
read from manifest JSON files and factory method to convert PluginManifest into ModuleDescriptor.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from camera_analytics.registry.descriptor import ModuleDescriptor, ModuleState
from camera_analytics.scheduler.policy import ExecutionMode, ExecutionPolicy


@dataclass(frozen=True, slots=True)
class PluginManifest:
    """Immutable metadata container representing parsed plugin manifest specification.

    Attributes:
        plugin_id: Unique string identifier for the plugin (e.g. 'people_counter_v1').
        name: Human-readable display name.
        version: Semantic version string (e.g. '1.0.0').
        sdk_version: Compatible Analytics SDK version constraint (e.g. '1.0.0').
        author: Developer or company author metadata.
        description: Purpose summary of plugin.
        entry_point: Python module / class path specification (e.g. 'plugins.people.PeopleCounterModule').
        capabilities: List of capability string identifiers required by plugin.
        execution_policy: Dictionary or ExecutionPolicy specifying timing rules.
        priority: Priority ordering integer (lower number means higher execution priority).
    """

    plugin_id: str
    name: str
    version: str
    sdk_version: str
    entry_point: str
    author: str = "Enterprise Analytics Team"
    description: str = "Analytics Plugin"
    capabilities: list[str] = field(default_factory=list)
    execution_policy: dict[str, Any] = field(default_factory=dict)
    priority: int = 100

    def to_descriptor(self) -> ModuleDescriptor:
        """Convert PluginManifest into ModuleDescriptor for ModuleRegistry registration.

        Returns:
            ModuleDescriptor instance configured with manifest metadata.
        """
        exec_dict = self.execution_policy or {}
        mode_str = exec_dict.get("execution_mode", "EVERY_FRAME").upper()
        try:
            mode = ExecutionMode[mode_str]
        except KeyError:
            mode = ExecutionMode.EVERY_FRAME

        policy = ExecutionPolicy(
            execution_mode=mode,
            interval=int(exec_dict.get("interval", 1)),
            priority=int(exec_dict.get("priority", self.priority)),
        )

        return ModuleDescriptor(
            module_id=self.plugin_id,
            module_name=self.name,
            version=self.version,
            author=self.author,
            description=self.description,
            capabilities=list(self.capabilities),
            priority=self.priority,
            enabled=True,
            state=ModuleState.REGISTERED,
            execution_policy=policy,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert manifest summary to dictionary."""
        return {
            "plugin_id": self.plugin_id,
            "name": self.name,
            "version": self.version,
            "sdk_version": self.sdk_version,
            "author": self.author,
            "description": self.description,
            "entry_point": self.entry_point,
            "capabilities": list(self.capabilities),
            "execution_policy": dict(self.execution_policy),
            "priority": self.priority,
        }
