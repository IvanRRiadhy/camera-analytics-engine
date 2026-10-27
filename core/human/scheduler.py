"""
Human Analytics Scheduler & Runtime Metrics.

Manages frame stride, interval scheduling, quality gating, lock status, DAG execution,
and collects detailed execution telemetry for each module.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence
import numpy as np
from numpy.typing import NDArray

from camera_analytics.core.human.base_module import BaseHumanAnalyticsModule
from camera_analytics.core.human.batch_queue import HumanBatchQueue, TimeoutBatchStrategy
from camera_analytics.core.human.context import HumanModuleContext
from camera_analytics.core.human.dependency_graph import ModuleDependencyGraph
from camera_analytics.core.human.models import HumanRepresentation, HumanState
from camera_analytics.core.human.model_manager import ModelManager
from camera_analytics.core.human.module_registry import ModuleRegistry
from camera_analytics.core.human.state_updater import HumanStateUpdater

logger = logging.getLogger(__name__)


from camera_analytics.core.human.profiler import InferenceProfiler
from camera_analytics.core.human.request import HumanInferenceRequest


@dataclass(frozen=True, slots=True)
class InferenceTask:
    """Decoupled inference task emitted by HumanAnalyticsScheduler for execution.

    Contains a batch of validated HumanInferenceRequest containers ready for module processing.
    """

    task_id: str
    module_id: str
    requests: tuple[HumanInferenceRequest, ...]
    priority: int = 1
    timestamp_utc: float = field(default_factory=time.time)

    @property
    def batch_size(self) -> int:
        return len(self.requests)


@dataclass
class ModuleExecutionMetrics:
    """Execution statistics and performance metrics for an AI module."""

    module_id: str
    execution_count: int = 0
    skipped_count: int = 0
    locked_count: int = 0
    enqueue_count: int = 0
    processed_count: int = 0
    successful_inference_count: int = 0
    failed_inference_count: int = 0
    total_latency_ms: float = 0.0
    preprocess_latency_ms: float = 0.0
    inference_latency_ms: float = 0.0
    postprocess_latency_ms: float = 0.0
    last_execution_timestamp: float = 0.0
    last_latency_ms: float = 0.0
    batch_size_last: int = 0
    batch_wait_time_ms: float = 0.0

    @property
    def average_latency_ms(self) -> float:
        """Return average execution latency in milliseconds."""
        return round(self.total_latency_ms / self.execution_count, 3) if self.execution_count > 0 else 0.0


class HumanAnalyticsScheduler:
    """DAG-based scheduler governing module execution order, quality gates, batch queues, and telemetry collection."""

    def __init__(
        self,
        model_manager: Optional[ModelManager] = None,
        registry: Optional[ModuleRegistry] = None,
        updater: Optional[HumanStateUpdater] = None,
        profiler: Optional[InferenceProfiler] = None,
    ) -> None:
        self.model_manager = model_manager or ModelManager()
        self.registry = registry or ModuleRegistry()
        self.graph = ModuleDependencyGraph()
        self.updater = updater or HumanStateUpdater()
        self.profiler = profiler or InferenceProfiler()
        self.metrics: dict[str, ModuleExecutionMetrics] = {}
        self._batch_queues: dict[str, HumanBatchQueue] = {}
        self._cached_order: Optional[list[str]] = None

    def register_module(
        self,
        module: BaseHumanAnalyticsModule,
        dependencies: Optional[list[str]] = None,
    ) -> None:
        """Register an AI module via ModuleRegistry and update dependency graph."""
        m_id = module.module_id
        self.registry.register_module(module)
        self.metrics[m_id] = ModuleExecutionMetrics(module_id=m_id)
        batch_sz = getattr(module.config, "batch_size", 1)
        self._batch_queues[m_id] = HumanBatchQueue(
            strategy=TimeoutBatchStrategy(),
            max_batch_size=batch_sz,
            timeout_ms=50.0,
        )
        self.graph.add_module(
            module_id=m_id,
            priority=module.config.priority,
            dependencies=dependencies or [],
        )
        self._cached_order = None
        module.initialize(self.model_manager)

    def execute_pipeline(
        self,
        representation: HumanRepresentation,
        state: HumanState,
        frame: Optional[NDArray[np.uint8]] = None,
        runtime_context: Optional[Any] = None,
        frame_index: int = 0,
        timestamp: float = 0.0,
    ) -> HumanState:
        """Execute all enabled modules in topological DAG order for a track."""
        modules = self.registry.list_modules()
        if not modules:
            return state

        if self._cached_order is None:
            self._cached_order = self.graph.resolve_execution_order()

        current_state = state

        for m_id in self._cached_order:
            module = self.registry.get_module(m_id)
            if module is None:
                continue

            m_metrics = self.metrics[m_id]
            b_queue = self._batch_queues[m_id]

            should_proc = module.should_process(
                representation=representation,
                state=current_state,
                frame_index=frame_index,
                timestamp=timestamp,
            )
            if should_proc:
                ctx = HumanModuleContext(
                    representation=representation,
                    state=current_state,
                    frame=frame,
                    runtime_context=runtime_context,
                )
                b_queue.enqueue(representation.track_id, ctx)
                m_metrics.enqueue_count += 1

            if b_queue.should_dispatch() or b_queue.queue_size >= 1:
                batch_payloads = b_queue.dequeue_batch()
                batch_contexts = [item.context for item in batch_payloads]
                
                t0 = time.perf_counter()
                try:
                    results = module.process_batch(batch_contexts)
                    latency = (time.perf_counter() - t0) * 1000.0

                    current_state = self.updater.update_state(current_state, results)

                    m_metrics.execution_count += len(batch_contexts)
                    m_metrics.processed_count += len(batch_contexts)
                    m_metrics.successful_inference_count += len(batch_contexts)
                    m_metrics.total_latency_ms += latency
                    m_metrics.last_latency_ms = round(latency, 3)
                    m_metrics.last_execution_timestamp = timestamp or time.time()
                    m_metrics.batch_size_last = len(batch_contexts)
                except Exception as exc:
                    m_metrics.failed_inference_count += len(batch_contexts)
                    logger.error("[HumanAnalyticsScheduler] Module '%s' batch execution failed: %s", m_id, exc, exc_info=True)
            else:
                if current_state.is_locked:
                    m_metrics.locked_count += 1
                else:
                    m_metrics.skipped_count += 1

        return current_state

    def get_metrics_summary(self) -> dict[str, dict[str, Any]]:
        """Return execution telemetry summary for all registered modules."""
        return {
            m_id: {
                "executionCount": m.execution_count,
                "skippedCount": m.skipped_count,
                "lockedCount": m.locked_count,
                "enqueueCount": m.enqueue_count,
                "processedCount": m.processed_count,
                "averageLatencyMs": m.average_latency_ms,
                "lastLatencyMs": m.last_latency_ms,
                "queueSize": self._batch_queues[m_id].queue_size if m_id in self._batch_queues else 0,
            }
            for m_id, m in self.metrics.items()
        }

    def cleanup(self) -> None:
        """Shutdown modules and unload model manager."""
        for module in self.registry.list_modules():
            module.cleanup()
        self.model_manager.unload_all()
        self.graph.clear()
        self.registry.clear()
        self._batch_queues.clear()

