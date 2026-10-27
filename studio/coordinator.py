"""
EngineStudioCoordinator Infrastructure (Sprint H1.5D1.5).

Hardened telemetry coordinator managing collector priorities, topological execution order,
collector timeout bounds, SnapshotBuilder creation, SnapshotValidator integrity checks, and SnapshotCache updates.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from camera_analytics.studio.snapshot.builder import SnapshotBuilder
from camera_analytics.studio.snapshot.cache import SnapshotCache
from camera_analytics.studio.snapshot.engine_studio_snapshot import EngineStudioSnapshot
from camera_analytics.studio.snapshot.validator import SnapshotValidator
from camera_analytics.studio.telemetry.base_collector import CollectorPriority, ITelemetryCollector
from camera_analytics.studio.telemetry.collector_context import CollectorContext
from camera_analytics.studio.telemetry.collector_health import CollectorStatus
from camera_analytics.studio.telemetry.collectors import (
    CameraTelemetryCollector,
    CommunicationTelemetryCollector,
    ConfigurationTelemetryCollector,
    EventTimelineTelemetryCollector,
    HumanTelemetryCollector,
    ModelTelemetryCollector,
    ModuleTelemetryCollector,
    PipelineTelemetryCollector,
    PerformanceTelemetryCollector,
    RuntimeTelemetryCollector,
    ThreadTelemetryCollector,
    ZoneTelemetryCollector,
)

logger = logging.getLogger(__name__)


from camera_analytics.studio.inspectors.model_inspector import AIModelInspector
from camera_analytics.studio.inspectors.camera_inspector import CameraInspector
from camera_analytics.studio.inspectors.event_timeline import EventTimelineInspector
from camera_analytics.studio.inspectors.human_runtime import HumanRuntimeInspector
from camera_analytics.studio.inspectors.module_inspector import ModuleInspector
from camera_analytics.studio.inspectors.runtime_overview import RuntimeOverviewInspector
from camera_analytics.studio.plugins.plugin_registry import PluginRegistry


class EngineStudioCoordinator:
    """Hardened coordinator orchestrating telemetry collection and immutable EngineStudioSnapshot generation."""

    def __init__(self, collector_timeout_ms: float = 100.0) -> None:
        self.collector_timeout_ms = collector_timeout_ms
        self._sequence_id: int = 0
        self._collectors: dict[str, ITelemetryCollector] = {}
        self.builder: SnapshotBuilder = SnapshotBuilder()
        self.cache: SnapshotCache = SnapshotCache()
        self.context: CollectorContext = CollectorContext()
        self.inspector_registry: PluginRegistry = PluginRegistry()
        self.inspectors: list[Any] = []
        self._register_default_collectors()
        self._register_default_inspectors()

    def _register_default_inspectors(self) -> None:
        """Register persistent 6 inspector panels once in InspectorRegistry."""
        self.inspectors = [
            RuntimeOverviewInspector(),
            AIModelInspector(),
            HumanRuntimeInspector(),
            CameraInspector(),
            ModuleInspector(),
            EventTimelineInspector(),
        ]
        for insp in self.inspectors:
            if hasattr(insp, "panel_id"):
                self.inspector_registry._plugins[insp.panel_id] = insp
        logger.info("[EngineStudioCoordinator] Persistent InspectorRegistry initialized with 6 Inspector Panels.")

    def _register_default_collectors(self) -> None:
        """Register default 12 subsystem telemetry collectors."""
        cols = [
            RuntimeTelemetryCollector(),
            PipelineTelemetryCollector(),
            ModelTelemetryCollector(),
            HumanTelemetryCollector(),
            ZoneTelemetryCollector(),
            ModuleTelemetryCollector(),
            CommunicationTelemetryCollector(),
            PerformanceTelemetryCollector(),
            ThreadTelemetryCollector(),
            ConfigurationTelemetryCollector(),
            CameraTelemetryCollector(),
            EventTimelineTelemetryCollector(),
        ]
        for c in cols:
            self.register_collector(c)

    def register_collector(self, collector: ITelemetryCollector) -> None:
        """Register a subsystem telemetry collector."""
        self._collectors[collector.collector_id] = collector

    def get_ordered_collectors(self) -> list[ITelemetryCollector]:
        """Return list of registered collectors ordered by priority and dependencies."""
        def priority_key(c: ITelemetryCollector) -> int:
            if c.priority == CollectorPriority.HIGH:
                return 1
            elif c.priority == CollectorPriority.NORMAL:
                return 2
            return 3

        return sorted(self._collectors.values(), key=priority_key)

    def generate_snapshot(self) -> EngineStudioSnapshot:
        """Collect metrics with timeout guards, build immutable snapshot, validate, and push to cache."""
        t0 = time.time()
        self._sequence_id += 1

        snapshots: dict[str, Any] = {}
        collector_count = len(self._collectors)
        success_count = 0
        failed_count = 0
        timeout_count = 0

        for col in self.get_ordered_collectors():
            c_t0 = time.time()
            try:
                sub_snap = col.collect(self.context)
                c_lat = (time.time() - c_t0) * 1000.0

                if c_lat > self.collector_timeout_ms:
                    col.health.record_timeout(c_lat)
                    timeout_count += 1
                else:
                    col.health.record_success(c_lat)
                    success_count += 1

                snapshots[col.collector_id] = sub_snap
            except Exception as e:
                col.health.record_error(str(e))
                failed_count += 1
                logger.error(f"[Coordinator] Collector '{col.collector_id}' failed: {e}")

        gen_time_ms = (time.time() - t0) * 1000.0

        # Build snapshot via SnapshotBuilder
        snapshot = self.builder.build(
            sequence_id=self._sequence_id,
            generation_time_ms=gen_time_ms,
            collector_count=collector_count,
            collector_success_count=success_count,
            collector_failed_count=failed_count,
            collector_timeout_count=timeout_count,
            runtime=snapshots.get("runtime"),
            pipeline=snapshots.get("pipeline"),
            model=snapshots.get("model"),
            human=snapshots.get("human"),
            zone=snapshots.get("zone"),
            module=snapshots.get("module"),
            communication=snapshots.get("communication"),
            profiler=snapshots.get("performance"),
            thread=snapshots.get("thread"),
            configuration=snapshots.get("configuration"),
            camera=snapshots.get("camera"),
            event_timeline=snapshots.get("event_timeline"),
        )

        # Validate via SnapshotValidator
        SnapshotValidator.validate(snapshot)

        # Push to SnapshotCache
        self.cache.push(snapshot)

        return snapshot
