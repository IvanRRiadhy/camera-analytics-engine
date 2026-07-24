"""
Execution Scheduler Core Component.

Provides ExecutionScheduler class evaluating whether an Analytics Module should be executed
on a specific frame index according to its ExecutionPolicy and ModuleState.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Optional

from camera_analytics.scheduler.policy import ExecutionMode, ExecutionPolicy

if TYPE_CHECKING:
    from camera_analytics.registry.descriptor import ModuleDescriptor

logger = logging.getLogger(__name__)


class ExecutionScheduler:
    """Central scheduler evaluating timing execution rules for Analytics Modules."""

    def __init__(self) -> None:
        pass

    def should_execute(self, descriptor: Any, frame_index: int) -> bool:
        """Determine if an Analytics Module should execute on the given frame_index.

        Args:
            descriptor: ModuleDescriptor containing state and execution_policy.
            frame_index: Sequential integer frame number.

        Returns:
            True if module should execute, False if it should be skipped.
        """
        # 1. Reject if module is administrative disabled or in invalid state
        if not getattr(descriptor, "enabled", True):
            return False

        state_name = getattr(getattr(descriptor, "state", None), "name", "")
        if state_name != "RUNNING":
            return False

        # 2. Retrieve execution_policy from descriptor (fallback to EVERY_FRAME if None)
        policy: ExecutionPolicy = getattr(descriptor, "execution_policy", None) or ExecutionPolicy()

        mode = policy.execution_mode

        # 3. Evaluate ExecutionMode
        if mode == ExecutionMode.DISABLED:
            return False

        if mode == ExecutionMode.EVERY_FRAME:
            return True

        if mode == ExecutionMode.INTERVAL:
            interval = max(1, policy.interval)
            # Execute on frame_index if frame_index is divisible by interval (or 1st frame)
            return (frame_index % interval == 0) or (frame_index == 1)

        if mode == ExecutionMode.MANUAL:
            # Manual mode requires explicit external trigger (default False per frame)
            return False

        if mode == ExecutionMode.ON_EVENT:
            # Reserved ON_EVENT mode TODO stub
            logger.debug("Scheduler: ON_EVENT mode for '%s' evaluated as False", getattr(descriptor, "module_id", "unknown"))
            return False

        return True
