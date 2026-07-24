"""
Execution Scheduler Policy Component.

Provides ExecutionMode enum and ExecutionPolicy dataclass specifying when and how frequently
an Analytics Module should be scheduled for execution by the Analytics Runtime Kernel.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any


class ExecutionMode(Enum):
    """Enumeration specifying execution timing modes for Analytics Modules."""

    EVERY_FRAME = auto()
    INTERVAL = auto()
    MANUAL = auto()
    DISABLED = auto()
    ON_EVENT = auto()  # Reserved TODO stub for future event-triggered execution


@dataclass(slots=True)
class ExecutionPolicy:
    """Execution policy specifying scheduling rules for an Analytics Module.

    Attributes:
        execution_mode: ExecutionMode enum indicating timing rule.
        interval: Number of frames between executions when mode is INTERVAL (default: 1).
        priority: Priority ordering integer (lower number means higher execution priority).
    """

    execution_mode: ExecutionMode = ExecutionMode.EVERY_FRAME
    interval: int = 1
    priority: int = 100

    def to_dict(self) -> dict[str, Any]:
        """Convert policy to dictionary summary."""
        return {
            "execution_mode": self.execution_mode.name,
            "interval": self.interval,
            "priority": self.priority,
        }
