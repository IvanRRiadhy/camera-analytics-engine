"""
Collector Health & Status Infrastructure (Sprint H1.5D1.5).

Defines the health model for subsystem telemetry collectors.
Ensures that collector failures or timeouts never freeze or crash the Studio.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class CollectorStatus(str, Enum):
    """Execution status enum for telemetry collectors."""

    ACTIVE = "ACTIVE"
    IDLE = "IDLE"
    ERROR = "ERROR"
    DISABLED = "DISABLED"
    TIMEOUT = "TIMEOUT"


@dataclass
class CollectorHealth:
    """Diagnostic health metrics for a telemetry collector."""

    collector_id: str
    status: CollectorStatus = CollectorStatus.ACTIVE
    last_collection_time: float = field(default_factory=time.time)
    last_success_time: float = field(default_factory=time.time)
    collection_latency_ms: float = 0.0
    failure_count: int = 0
    timeout_count: int = 0
    error_message: Optional[str] = None

    def record_success(self, latency_ms: float) -> None:
        self.status = CollectorStatus.ACTIVE
        now = time.time()
        self.last_collection_time = now
        self.last_success_time = now
        self.collection_latency_ms = latency_ms
        self.error_message = None

    def record_timeout(self, latency_ms: float) -> None:
        self.status = CollectorStatus.TIMEOUT
        self.last_collection_time = time.time()
        self.collection_latency_ms = latency_ms
        self.timeout_count += 1
        self.error_message = f"Collection timed out (> {latency_ms:.1f}ms)"

    def record_error(self, err_msg: str) -> None:
        self.status = CollectorStatus.ERROR
        self.last_collection_time = time.time()
        self.failure_count += 1
        self.error_message = err_msg
