"""
Analytics Runtime Kernel Package.

Provides the isolated Analytics Runtime Kernel Skeleton for managing Analytics Module lifecycles,
context dependency injection, and exception-isolated Scene snapshot processing.
"""

from camera_analytics.runtime.context import RuntimeContext
from camera_analytics.runtime.execution import ExecutionEngine
from camera_analytics.runtime.kernel import AnalyticsRuntime
from camera_analytics.runtime.lifecycle import LifecycleManager, ModuleState

__all__ = [
    "RuntimeContext",
    "ModuleState",
    "LifecycleManager",
    "ExecutionEngine",
    "AnalyticsRuntime",
]
