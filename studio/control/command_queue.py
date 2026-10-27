"""
StudioCommandQueue Placeholder Infrastructure (Sprint H1.5D1.5).

Provides StudioCommand and StudioCommandQueue for enqueueing future Control Plane engine commands
without executing engine modifications in this sprint.
"""

from __future__ import annotations

import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class CommandType(str, Enum):
    """Supported control plane command types."""

    RELOAD_CONFIG = "RELOAD_CONFIG"
    PAUSE_PIPELINE = "PAUSE_PIPELINE"
    RESUME_PIPELINE = "RESUME_PIPELINE"
    RELOAD_MODEL = "RELOAD_MODEL"
    UNLOAD_MODEL = "UNLOAD_MODEL"
    BENCHMARK_START = "BENCHMARK_START"
    BENCHMARK_STOP = "BENCHMARK_STOP"
    REPLAY_RECORDING = "REPLAY_RECORDING"


@dataclass(frozen=True, slots=True)
class StudioCommand:
    """Control plane command object."""

    command_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    command_type: CommandType = CommandType.RELOAD_CONFIG
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp_utc: float = field(default_factory=time.time)
    status: str = "QUEUED"               # "QUEUED" | "EXECUTING" | "COMPLETED" | "FAILED"


class StudioCommandQueue:
    """Thread-safe queue storing queued control plane commands for future execution."""

    def __init__(self, max_capacity: int = 50) -> None:
        self.max_capacity = max_capacity
        self._queue: deque[StudioCommand] = deque(maxlen=max_capacity)

    def enqueue(self, command: StudioCommand) -> None:
        """Enqueue a control plane command."""
        self._queue.append(command)

    def dequeue(self) -> Optional[StudioCommand]:
        """Dequeue the next command for execution."""
        if self._queue:
            return self._queue.popleft()
        return None

    def peek_all(self) -> list[StudioCommand]:
        """Return list of queued commands without removing them."""
        return list(self._queue)

    def __len__(self) -> int:
        return len(self._queue)
