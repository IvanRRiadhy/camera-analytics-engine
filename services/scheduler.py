"""
Service Scheduler Implementation.

Supports `SCHEDULED` execution mode for cron / periodic interval background tasks.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class ServiceScheduler:
    """Schedules periodic background tasks for scheduled services."""

    def __init__(self) -> None:
        self._tasks: list[tuple[float, Callable[[], None]]] = []
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._is_running = False

    def schedule_interval(self, interval_sec: float, task_fn: Callable[[], None]) -> None:
        """Schedule a task function to run every interval_sec seconds."""
        with self._lock:
            self._tasks.append((interval_sec, task_fn))

    def start(self) -> None:
        """Start scheduler thread."""
        if self._is_running:
            return
        self._is_running = True
        self._thread = threading.Thread(target=self._scheduler_loop, daemon=True, name="ServiceScheduler")
        self._thread.start()
        logger.info("ServiceScheduler started")

    def _scheduler_loop(self) -> None:
        """Loop evaluating interval tasks."""
        last_runs: dict[int, float] = {}

        while self._is_running:
            now = time.time()
            with self._lock:
                task_list = list(self._tasks)

            for idx, (interval, task_fn) in enumerate(task_list):
                last_ts = last_runs.get(idx, 0.0)
                if (now - last_ts) >= interval:
                    try:
                        task_fn()
                    except Exception as exc:
                        logger.error("ServiceScheduler task execution error: %s", exc)
                    last_runs[idx] = now

            time.sleep(0.5)

    def stop(self) -> None:
        """Stop scheduler thread."""
        self._is_running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        logger.info("ServiceScheduler stopped")
