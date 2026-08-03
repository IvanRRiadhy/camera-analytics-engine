"""
Service Execution Engine Implementation.

Dedicated worker engine managing immediate, async, or batch event handlers with retries and exception isolation.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from typing import Optional

from camera_analytics.communication.models import StandardAnalyticsEvent
from camera_analytics.eventing.models import PlatformEvent
from camera_analytics.services.lifecycle import ServiceLifecycleState
from camera_analytics.services.registry import ServiceRegistryEntry

logger = logging.getLogger(__name__)


class ServiceExecutionEngine:
    """Worker engine executing events across service plugins with retries and exception isolation."""

    def __init__(self, max_workers: int = 4) -> None:
        self.max_workers = max_workers
        self._queue: queue.Queue[tuple[ServiceRegistryEntry, StandardAnalyticsEvent | PlatformEvent]] = queue.Queue(maxsize=5000)
        self._workers: list[threading.Thread] = []
        self._is_running = False

    def start(self) -> None:
        """Start worker threads."""
        if self._is_running:
            return
        self._is_running = True
        for i in range(self.max_workers):
            t = threading.Thread(target=self._worker_loop, daemon=True, name=f"ServiceWorker-{i}")
            t.start()
            self._workers.append(t)
        logger.info("ServiceExecutionEngine started %d worker threads", self.max_workers)

    def execute_event(
        self,
        entry: ServiceRegistryEntry,
        event: StandardAnalyticsEvent | PlatformEvent,
    ) -> None:
        """Execute event on target service plugin according to execution_mode."""
        if entry.manifest.execution_mode == "IMMEDIATE":
            self._safe_execute(entry, event)
        else:
            try:
                self._queue.put_nowait((entry, event))
            except queue.Full:
                logger.warning("ServiceExecutionEngine queue full! Dropped event for service '%s'", entry.manifest.service_name)

    def _worker_loop(self) -> None:
        """Worker thread processing queued events."""
        while self._is_running:
            try:
                entry, event = self._queue.get(timeout=0.2)
                self._safe_execute(entry, event)
                self._queue.task_done()
            except queue.Empty:
                continue

    def _safe_execute(
        self,
        entry: ServiceRegistryEntry,
        event: StandardAnalyticsEvent | PlatformEvent,
    ) -> None:
        """Execute on_event with retry policy and Exception Isolation barrier."""
        manifest = entry.manifest
        service = entry.instance
        policy = manifest.retry_policy

        attempts = 0
        max_attempts = max(1, policy.max_retries)

        while attempts < max_attempts:
            attempts += 1
            try:
                service.on_event(event)
                return
            except Exception as exc:
                entry.error_count += 1
                entry.last_error = str(exc)
                logger.error(
                    "ServiceExecutionEngine: Exception barrier caught crash in '%s' (Attempt %d/%d): %s",
                    manifest.service_name,
                    attempts,
                    max_attempts,
                    exc,
                )
                if attempts < max_attempts and policy.backoff_sec > 0:
                    time.sleep(policy.backoff_sec)

        entry.state = ServiceLifecycleState.FAILED

    def stop(self) -> None:
        """Stop worker threads cleanly."""
        self._is_running = False
        for t in self._workers:
            if t.is_alive():
                t.join(timeout=1.0)
        self._workers.clear()
        logger.info("ServiceExecutionEngine stopped cleanly")
