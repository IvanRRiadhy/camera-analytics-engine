"""
Attribute Lock Manager & State Machine (Sprint H1.5A).

Manages per-attribute lock states (UNLOCKED, LOCKING, LOCKED, EXPIRED) to allow modules
to skip processing locked attributes (e.g. Gender LOCKED, Age UNLOCKED).
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class AttributeLockState(str, Enum):
    """Lock state enumeration for Human Analytics domain attributes."""

    UNLOCKED = "UNLOCKED"
    LOCKING = "LOCKING"
    LOCKED = "LOCKED"
    EXPIRED = "EXPIRED"


class AttributeLockManager:
    """Manages per-attribute lock state transitions for track states."""

    @staticmethod
    def is_locked(current_lock: str) -> bool:
        """Check if attribute is currently locked."""
        return current_lock in (AttributeLockState.LOCKED.value, AttributeLockState.LOCKED)

    @staticmethod
    def should_process(current_lock: str) -> bool:
        """Return True if attribute is eligible for module processing."""
        return current_lock in (
            AttributeLockState.UNLOCKED.value,
            AttributeLockState.UNLOCKED,
            AttributeLockState.EXPIRED.value,
            AttributeLockState.EXPIRED,
        )

    @staticmethod
    def transition(current_lock: str, action: str) -> str:
        """Evaluate lock state machine transition."""
        cur = current_lock.upper() if isinstance(current_lock, str) else current_lock.value
        act = action.upper()

        if act == "LOCK":
            return AttributeLockState.LOCKED.value
        elif act == "LOCKING":
            return AttributeLockState.LOCKING.value
        elif act == "EXPIRE":
            return AttributeLockState.EXPIRED.value
        elif act == "UNLOCK":
            return AttributeLockState.UNLOCKED.value

        return cur
