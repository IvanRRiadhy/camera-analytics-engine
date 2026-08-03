"""
Unified Runtime Event Bus for decoupled, fault-isolated event propagation.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
import traceback
from typing import Any, Optional

from camera_analytics.events.models import BaseRuntimeEvent
from camera_analytics.events.subscribers import EventSubscriber

logger = logging.getLogger(__name__)


class RuntimeEventBus:
    """Enterprise Publish-Subscribe Event Bus providing isolated event dispatching and observability metrics."""

    _instance: Optional[RuntimeEventBus] = None
    _lock = threading.RLock()

    def __init__(self, queue_max_size: int = 10000) -> None:
        self._type_subscribers: dict[str, list[EventSubscriber]] = {}
        self._wildcard_subscribers: list[EventSubscriber] = []

        self._queue: queue.Queue[BaseRuntimeEvent] = queue.Queue(maxsize=queue_max_size)
        self._worker_thread: Optional[threading.Thread] = None
        self._running = False

        # Observability Metrics
        self.events_published: int = 0
        self.events_dropped: int = 0
        self.dispatch_failures: int = 0
        self.total_publish_time_ms: float = 0.0

        self.start()

    @classmethod
    def get_instance(cls) -> RuntimeEventBus:
        """Singleton accessor for global RuntimeEventBus instance."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = RuntimeEventBus()
            return cls._instance

    def subscribe(self, event_type: str, subscriber: EventSubscriber) -> None:
        """Subscribe a listener to a specific event_type."""
        with self._lock:
            if event_type == "*":
                if subscriber not in self._wildcard_subscribers:
                    self._wildcard_subscribers.append(subscriber)
            else:
                if event_type not in self._type_subscribers:
                    self._type_subscribers[event_type] = []
                if subscriber not in self._type_subscribers[event_type]:
                    self._type_subscribers[event_type].append(subscriber)
            logger.info("[RuntimeEventBus] Subscribed '%s' to event_type '%s'.", subscriber.name, event_type)

    def subscribe_all(self, subscriber: EventSubscriber) -> None:
        """Subscribe a listener to all event types via wildcard."""
        self.subscribe("*", subscriber)

    def publish(self, event: BaseRuntimeEvent) -> None:
        """Publish a runtime event onto the asynchronous event bus."""
        start_t = time.perf_counter()

        try:
            self._queue.put_nowait(event)
            self.events_published += 1
        except queue.Full:
            self.events_dropped += 1
            logger.warning("[RuntimeEventBus] Queue full (%d events)! Dropped event '%s'.", self._queue.maxsize, event.event_id)

        elapsed_ms = (time.perf_counter() - start_t) * 1000.0
        self.total_publish_time_ms += elapsed_ms

    def start(self) -> None:
        """Start background event dispatcher worker thread."""
        with self._lock:
            if not self._running:
                self._running = True
                self._worker_thread = threading.Thread(target=self._dispatch_loop, daemon=True, name="RuntimeEventBusWorker")
                self._worker_thread.start()
                logger.info("[RuntimeEventBus] Background dispatcher thread started.")

    def stop(self) -> None:
        """Stop background event dispatcher worker thread."""
        with self._lock:
            self._running = False

    def _dispatch_loop(self) -> None:
        """Background thread popping events and routing to subscribers with complete fault isolation."""
        while self._running:
            try:
                event = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue

            targets: list[EventSubscriber] = []
            with self._lock:
                targets.extend(self._wildcard_subscribers)
                targets.extend(self._type_subscribers.get(event.event_type, []))

            # Dispatch to subscribers with isolated exception handling
            for sub in targets:
                try:
                    sub.handle_event(event)
                except Exception as exc:
                    self.dispatch_failures += 1
                    logger.error(
                        "[RuntimeEventBus] Isolated exception in subscriber '%s' for event '%s': %s\n%s",
                        sub.name,
                        event.event_id,
                        exc,
                        traceback.format_exc(),
                    )

            self._queue.task_done()

    def get_metrics(self) -> dict[str, Any]:
        """Return runtime observability metrics for the Event Bus."""
        avg_pub_ms = (self.total_publish_time_ms / self.events_published) if self.events_published > 0 else 0.0
        return {
            "events_published": self.events_published,
            "events_dropped": self.events_dropped,
            "queue_depth": self._queue.qsize(),
            "dispatch_failures": self.dispatch_failures,
            "average_publish_time_ms": round(avg_pub_ms, 3),
            "subscribers_count": len(self._wildcard_subscribers) + sum(len(v) for v in self._type_subscribers.values()),
        }
