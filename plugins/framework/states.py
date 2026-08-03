"""
Plugin Lifecycle States for camera_analytics framework.
"""

from __future__ import annotations

from enum import Enum, auto


class PluginState(Enum):
    """Lifecycle state machine for dynamically loaded vision plugins."""

    INSTALLED = auto()
    VERIFIED = auto()
    LOADED = auto()
    INITIALIZED = auto()
    WARMUP = auto()
    RUNNING = auto()
    PAUSED = auto()
    STOPPING = auto()
    STOPPED = auto()
    FAILED = auto()
    RESTARTING = auto()
