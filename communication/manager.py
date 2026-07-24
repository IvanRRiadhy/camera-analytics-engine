"""
Communication Manager and Event Queue Coordinator.

Central singleton controller managing the thread-safe `PublishQueue`, background worker thread,
and `PublisherManager`. Guarantees non-blocking event emission for AI Pipeline processing loops,
tracks communication runtime metrics, and handles graceful shutdown.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

from camera_analytics.communication.models import (
    AnalyticsEventSerializer,
    StandardAnalyticsEvent,
)
from camera_analytics.communication.publisher_base import EventPublisher
from camera_analytics.communication.publisher_manager import PublisherManager

logger = logging.getLogger(__name__)


@dataclass
class CommunicationMetrics:
    """Runtime performance and status metrics for the Event Communication Layer."""

    total_events: int = 0
    published_events: int = 0
    failed_events: int = 0
    queue_size: int = 0
    dropped_events: int = 0
    publisher_errors: int = 0
    retry_count: int = 0
    avg_publish_time_ms: float = 0.0


class CommunicationManager:
    """Central singleton coordinator for event publishing.

    Features:
        - Non-blocking event enqueueing (`enqueue`).
        - Thread-safe bounded Queue (`queue_size`).
        - Background worker thread processing events asynchronously.
        - Runtime performance metrics calculation.
        - Graceful flush and shutdown.
    """

    _instance: Optional[CommunicationManager] = None
    _instance_lock = threading.Lock()

    def __init__(self, queue_size: int = 10000, worker_threads: int = 1) -> None:
        self._queue_size = queue_size
        self._worker_threads_count = worker_threads
        self._queue: queue.Queue[StandardAnalyticsEvent] = queue.Queue(maxsize=queue_size)

        self._publisher_manager = PublisherManager()
        self._serializer = AnalyticsEventSerializer()

        self._is_initialized = False
        self._is_running = False
        self._stop_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None

        # Metrics
        self._metrics_lock = threading.Lock()
        self._total_events = 0
        self._published_events = 0
        self._failed_events = 0
        self._dropped_events = 0
        self._publisher_errors = 0
        self._publish_times: list[float] = []

    @classmethod
    def get_instance(cls, queue_size: int = 10000) -> CommunicationManager:
        """Retrieve global singleton instance of CommunicationManager."""
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls(queue_size=queue_size)
            return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton instance (used in testing)."""
        with cls._instance_lock:
            if cls._instance is not None:
                cls._instance.dispose()
                cls._instance = None

    @property
    def publisher_manager(self) -> PublisherManager:
        """Reference to internal PublisherManager."""
        return self._publisher_manager

    @property
    def is_running(self) -> bool:
        """Whether the communication manager and worker thread are running."""
        return self._is_running

    def initialize(self, config: dict[str, Any]) -> None:
        """Initialize communication manager and publisher manager from configuration.

        Args:
            config: Communication configuration dictionary.
        """
        if self._is_initialized:
            return

        comm_cfg = config.get("communication", {})
        self._queue_size = comm_cfg.get("queue_size", self._queue_size)
        if self._queue.maxsize != self._queue_size:
            self._queue = queue.Queue(maxsize=self._queue_size)

        # Load publishers from config
        pub_configs = config.get("publishers", [])
        if pub_configs:
            self._publisher_manager.load_from_config(pub_configs)

        self._is_initialized = True
        logger.info("CommunicationManager initialized (queue_size=%d)", self._queue_size)

    def start(self) -> None:
        """Start background worker thread and publisher manager."""
        if self._is_running:
            return

        if not self._is_initialized:
            self.initialize({})

        self._publisher_manager.start()
        self._stop_event.clear()

        self._worker_thread = threading.Thread(
            target=self._worker_loop, daemon=True, name="CommunicationWorker"
        )
        self._worker_thread.start()
        self._is_running = True
        logger.info("CommunicationManager started background worker thread")

    def enqueue(self, event: StandardAnalyticsEvent) -> bool:
        """Enqueue an Analytics Event for asynchronous publishing without blocking AI Pipeline.

        Args:
            event: StandardAnalyticsEvent instance.

        Returns:
            True if enqueued successfully, False if queue is full and event was dropped.
        """
        if not self._is_running or self._stop_event.is_set():
            return False

        with self._metrics_lock:
            self._total_events += 1

        try:
            self._queue.put_nowait(event)
            return True
        except queue.Full:
            # Non-blocking queue overflow protection: drop event safely
            with self._metrics_lock:
                self._dropped_events += 1
            logger.warning(
                "CommunicationManager Queue FULL (%d/%d). Event '%s' dropped.",
                self._queue.qsize(), self._queue_size, event.event_type
            )
            return False

    def get_metrics(self) -> CommunicationMetrics:
        """Retrieve current runtime metrics snapshot."""
        with self._metrics_lock:
            avg_time = (sum(self._publish_times) / max(len(self._publish_times), 1)) if self._publish_times else 0.0
            return CommunicationMetrics(
                total_events=self._total_events,
                published_events=self._published_events,
                failed_events=self._failed_events,
                queue_size=self._queue.qsize(),
                dropped_events=self._dropped_events,
                publisher_errors=self._publisher_errors,
                retry_count=0,
                avg_publish_time_ms=avg_time,
            )

    def stop(self) -> None:
        """Flush pending queue items and stop worker thread cleanly."""
        if not self._is_running:
            return

        logger.info("CommunicationManager stopping. Flushing %d remaining queue items...", self._queue.qsize())
        self._stop_event.set()

        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=3.0)

        # Flush remaining queue items
        self._flush_queue_remaining()

        self._publisher_manager.stop()
        self._is_running = False
        logger.info("CommunicationManager stopped cleanly")

    def dispose(self) -> None:
        """Dispose communication manager and publisher resources."""
        if self._is_running:
            self.stop()

        self._publisher_manager.dispose()
        self._is_initialized = False
        logger.info("CommunicationManager disposed")

    # --- Internal Background Worker Loop ---

    def _worker_loop(self) -> None:
        """Background thread loop that dequeues events, serializes, and broadcasts to publishers."""
        while not self._stop_event.is_set() or not self._queue.empty():
            try:
                event = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue

            t0 = time.monotonic()
            try:
                # Step 1: Standardized Serialization
                json_payload = self._serializer.serialize(event)

                # Step 2: Broadcast to all active publishers
                succ, fail = self._publisher_manager.broadcast(event, json_payload)

                t1 = time.monotonic()
                duration_ms = (t1 - t0) * 1000.0

                with self._metrics_lock:
                    self._published_events += succ
                    self._failed_events += fail
                    self._publish_times.append(duration_ms)
                    if len(self._publish_times) > 100:
                        self._publish_times.pop(0)

            except Exception as exc:
                with self._metrics_lock:
                    self._publisher_errors += 1
                logger.error("CommunicationWorker error processing event: %s", exc)

            finally:
                self._queue.task_done()

    def _flush_queue_remaining(self) -> None:
        """Process remaining items left in queue during shutdown."""
        while not self._queue.empty():
            try:
                event = self._queue.get_nowait()
                json_payload = self._serializer.serialize(event)
                succ, fail = self._publisher_manager.broadcast(event, json_payload)
                with self._metrics_lock:
                    self._published_events += succ
                    self._failed_events += fail
                self._queue.task_done()
            except queue.Empty:
                break
            except Exception as exc:
                logger.error("Error flushing queue event: %s", exc)
