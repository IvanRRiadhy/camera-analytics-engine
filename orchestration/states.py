"""
Sprint 11.2 Orchestration Domain State Enums.

Defines immutable state enums for Camera Sessions and Pipeline Instances.
"""

from __future__ import annotations

from enum import Enum, auto


class CameraSessionState(Enum):
    """Lifecycle states for a Camera Session.

    Attributes:
        CREATED: Initial state upon session creation.
        CONNECTING: Attempting to connect to stream source.
        READY: Stream source connected and validated.
        RUNNING: Actively streaming and processing.
        PAUSED: Stream paused.
        STOPPED: Cleanly shut down.
        FAILED: Encountered unrecoverable connection or stream error.
    """

    CREATED = auto()
    CONNECTING = auto()
    READY = auto()
    RUNNING = auto()
    PAUSED = auto()
    STOPPED = auto()
    FAILED = auto()


class PipelineState(Enum):
    """Lifecycle states for a Pipeline Instance.

    Attributes:
        CREATED: Initial state upon pipeline creation.
        INITIALIZED: Pipeline components configured.
        READY: Ready for execution loop.
        RUNNING: Execution loop active.
        PAUSED: Execution loop suspended.
        STOPPED: Pipeline cleanly stopped.
        FAILED: Pipeline execution error.
    """

    CREATED = auto()
    INITIALIZED = auto()
    READY = auto()
    RUNNING = auto()
    PAUSED = auto()
    STOPPED = auto()
    FAILED = auto()
