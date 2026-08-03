"""
Service Lifecycle States.

Defines `ServiceLifecycleState` enum representing the operational state of a service plugin.
"""

from __future__ import annotations

from enum import Enum


class ServiceLifecycleState(str, Enum):
    """Lifecycle states for Event Services."""

    UNINITIALIZED = "UNINITIALIZED"
    INITIALIZED = "INITIALIZED"
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    FAILED = "FAILED"
    UNSUPPORTED = "UNSUPPORTED"
