"""
StudioEventBus Infrastructure (Sprint H1.5D1.5).

Internal event bus managing UI and control plane events within the Studio.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class StudioEventType(str, Enum):
    """Event types for internal Studio communications."""

    TAB_CHANGED = "TAB_CHANGED"
    WORKSPACE_CHANGED = "WORKSPACE_CHANGED"
    CAMERA_SELECTED = "CAMERA_SELECTED"
    TRACK_SELECTED = "TRACK_SELECTED"
    RECORDING_STARTED = "RECORDING_STARTED"
    RECORDING_STOPPED = "RECORDING_STOPPED"
    COMMAND_QUEUED = "COMMAND_QUEUED"


@dataclass(frozen=True, slots=True)
class StudioEvent:
    """Internal Studio Event DTO."""

    event_type: StudioEventType
    payload: dict[str, Any] = field(default_factory=dict)


class StudioEventBus:
    """Publish-subscribe event bus for Studio UI components."""

    def __init__(self) -> None:
        self._subscribers: dict[StudioEventType, list[Callable[[StudioEvent], None]]] = {}

    def subscribe(self, event_type: StudioEventType, listener: Callable[[StudioEvent], None]) -> None:
        """Subscribe to a Studio event type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(listener)

    def publish(self, event: StudioEvent) -> None:
        """Publish a Studio event to subscribers."""
        listeners = self._subscribers.get(event.event_type, [])
        for listener in listeners:
            try:
                listener(event)
            except Exception as e:
                logger.error(f"[StudioEventBus] Error notifying subscriber for '{event.event_type}': {e}")
