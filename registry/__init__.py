"""
Module Registry Package.

Provides isolated Module Registry & Module Management layer, including ModuleDescriptor metadata,
ModuleState enum, ModuleRegistry store, and ModuleManager orchestrator.
"""

from camera_analytics.registry.descriptor import ModuleDescriptor, ModuleState
from camera_analytics.registry.manager import ModuleManager
from camera_analytics.registry.store import ModuleRegistry

__all__ = [
    "ModuleDescriptor",
    "ModuleState",
    "ModuleRegistry",
    "ModuleManager",
]
