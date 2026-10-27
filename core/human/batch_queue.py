"""
Human Analytics Batch Queue & Extensible Batching Strategies (Sprint H1.5A).

Provides IBatchingStrategy (FixedBatchStrategy, DynamicBatchStrategy, TimeoutBatchStrategy)
and HumanBatchQueue for collecting eligible track payloads into production inference batches.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

from camera_analytics.core.human.context import HumanModuleContext

logger = logging.getLogger(__name__)


@dataclass
class BatchPayload:
    """Payload item in the batch queue."""

    track_id: int
    context: HumanModuleContext
    enqueued_timestamp: float = field(default_factory=time.time)


class IBatchingStrategy(ABC):
    """Abstract Strategy interface for queue batching decisions."""

    @abstractmethod
    def should_dispatch(self, queue: list[BatchPayload], max_batch_size: int, timeout_ms: float) -> bool:
        """Return True if the current queue should be dispatched for module processing."""
        pass


class FixedBatchStrategy(IBatchingStrategy):
    """Dispatches when queue size reaches preferred fixed batch size."""

    def should_dispatch(self, queue: list[BatchPayload], max_batch_size: int, timeout_ms: float) -> bool:
        return len(queue) >= max_batch_size


class DynamicBatchStrategy(IBatchingStrategy):
    """Dispatches dynamically based on workload and queue depth."""

    def should_dispatch(self, queue: list[BatchPayload], max_batch_size: int, timeout_ms: float) -> bool:
        if not queue:
            return False
        return len(queue) >= max_batch_size


class TimeoutBatchStrategy(IBatchingStrategy):
    """Dispatches when batch size is met OR when oldest item exceeds timeout_ms."""

    def should_dispatch(self, queue: list[BatchPayload], max_batch_size: int, timeout_ms: float) -> bool:
        if not queue:
            return False
        if len(queue) >= max_batch_size:
            return True
        oldest_age_ms = (time.time() - queue[0].enqueued_timestamp) * 1000.0
        return oldest_age_ms >= timeout_ms


class HumanBatchQueue:
    """Production batch queue orchestrating queue collection and strategy-based dispatching."""

    def __init__(
        self,
        strategy: Optional[IBatchingStrategy] = None,
        max_batch_size: int = 8,
        timeout_ms: float = 50.0,
    ) -> None:
        self.strategy = strategy or TimeoutBatchStrategy()
        self.max_batch_size = max_batch_size
        self.timeout_ms = timeout_ms
        self._queue: list[BatchPayload] = []
        self._enqueue_count = 0
        self._processed_count = 0

    def enqueue(self, track_id: int, context: HumanModuleContext) -> None:
        """Enqueue a track context payload."""
        self._queue.append(BatchPayload(track_id=track_id, context=context))
        self._enqueue_count += 1

    def should_dispatch(self) -> bool:
        """Evaluate batching strategy to decide whether to dispatch."""
        return self.strategy.should_dispatch(
            queue=self._queue,
            max_batch_size=self.max_batch_size,
            timeout_ms=self.timeout_ms,
        )

    def dequeue_batch(self) -> list[BatchPayload]:
        """Dequeue up to max_batch_size payloads for processing."""
        batch = self._queue[: self.max_batch_size]
        self._queue = self._queue[self.max_batch_size :]
        self._processed_count += len(batch)
        return batch

    def clear(self) -> None:
        """Clear queue."""
        self._queue.clear()

    @property
    def queue_size(self) -> int:
        return len(self._queue)

    @property
    def enqueue_count(self) -> int:
        return self._enqueue_count

    @property
    def processed_count(self) -> int:
        return self._processed_count
