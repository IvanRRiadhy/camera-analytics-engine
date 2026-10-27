"""
Abstract Telemetry Collector Interface (Sprint H1.5D1.5).

Defines the ITelemetryCollector interface with explicit CollectorContext passing,
health diagnostics, priority scheduling, and DAG dependencies.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Optional

from camera_analytics.studio.telemetry.collector_context import CollectorContext
from camera_analytics.studio.telemetry.collector_health import CollectorHealth, CollectorStatus


class CollectorPriority(str, Enum):
    """Scheduling priority for telemetry collectors."""

    HIGH = "HIGH"
    NORMAL = "NORMAL"
    LOW = "LOW"


class ITelemetryCollector(ABC):
    """Abstract interface for all subsystem telemetry collectors."""

    def __init__(self) -> None:
        self.health: CollectorHealth = CollectorHealth(collector_id=self.collector_id)

    @property
    @abstractmethod
    def collector_id(self) -> str:
        """Unique identifier for this telemetry collector."""
        pass

    @property
    def priority(self) -> CollectorPriority:
        """Scheduling priority for this collector."""
        return CollectorPriority.NORMAL

    @property
    def dependencies(self) -> tuple[str, ...]:
        """IDs of collectors that must run before this collector."""
        return ()

    @abstractmethod
    def collect(self, context: Optional[CollectorContext] = None) -> Any:
        """Collect current metrics using explicit CollectorContext and return an immutable snapshot."""
        pass
