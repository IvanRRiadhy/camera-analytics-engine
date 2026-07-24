"""
Module Descriptor Component.

Provides ModuleState enum and ModuleDescriptor dataclass representing metadata, capabilities,
priority, enabling state, execution policy, and lifecycle status for Analytics Modules registered within the platform.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

from camera_analytics.scheduler.policy import ExecutionPolicy


class ModuleState(Enum):
    """Lifecycle and operational states for Analytics Modules in the Module Registry."""

    REGISTERED = auto()
    INITIALIZED = auto()
    RUNNING = auto()
    STOPPED = auto()
    DISPOSED = auto()
    FAILED = auto()
    DISABLED = auto()
    UNSUPPORTED = auto()


@dataclass(slots=True)
class ModuleDescriptor:
    """Descriptor metadata and status container for a registered Analytics Module.

    Attributes:
        module_id: Unique string identifier for the module (e.g. 'people_counter_v1').
        module_name: Human-readable display name.
        version: Semantic version string (e.g. '1.0.0').
        author: Module developer / author metadata.
        description: Summary of module purpose.
        capabilities: List of capability strings provided by this module (e.g. ['PEOPLE_COUNT', 'ZONE_ENTRY']).
        priority: Execution priority integer (lower value means higher execution priority).
        enabled: Boolean flag indicating if module is administrative enabled.
        state: Current ModuleState enum status.
        execution_policy: ExecutionPolicy dataclass defining timing scheduling rules.
    """

    module_id: str
    module_name: str
    version: str = "1.0.0"
    author: str = "Enterprise Camera Analytics Team"
    description: str = "Analytics Module"
    capabilities: list[str] = field(default_factory=list)
    priority: int = 100
    enabled: bool = True
    state: ModuleState = ModuleState.REGISTERED
    execution_policy: ExecutionPolicy = field(default_factory=ExecutionPolicy)

    def to_dict(self) -> dict[str, Any]:
        """Convert descriptor summary to dictionary."""
        return {
            "module_id": self.module_id,
            "module_name": self.module_name,
            "version": self.version,
            "author": self.author,
            "description": self.description,
            "capabilities": list(self.capabilities),
            "priority": self.priority,
            "enabled": self.enabled,
            "state": self.state.name,
            "execution_policy": self.execution_policy.to_dict(),
        }
