"""
Execution Scheduler Package.

Provides ExecutionMode enum, ExecutionPolicy dataclass, and ExecutionScheduler
for scheduling timing rules of Analytics Modules executed by the Analytics Runtime Kernel.
"""

from camera_analytics.scheduler.core import ExecutionScheduler
from camera_analytics.scheduler.policy import ExecutionMode, ExecutionPolicy

__all__ = [
    "ExecutionMode",
    "ExecutionPolicy",
    "ExecutionScheduler",
]
