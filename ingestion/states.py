"""
Sprint 11.3 Ingestion Domain States Enum.

Defines immutable state enum for Video Reader Background Workers.
"""

from __future__ import annotations

from enum import Enum, auto


class ReaderState(Enum):
    """Lifecycle states for a Video Reader Background Worker.

    Attributes:
        CREATED: Initial state upon worker instantiation.
        INITIALIZED: Video source and decoder initialized.
        READING: Actively reading stream and producing frames.
        RECONNECTING: Stream lost, attempting auto-reconnect backoff.
        STOPPED: Worker cleanly stopped.
        FAILED: Encountered unrecoverable stream error after max retries.
    """

    CREATED = auto()
    INITIALIZED = auto()
    READING = auto()
    RECONNECTING = auto()
    STOPPED = auto()
    FAILED = auto()
