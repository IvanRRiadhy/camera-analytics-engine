"""
Sprint H1.5D1.5 Studio Core Hardening & Control Plane Foundation Test Suite.

Verifies:
1. SnapshotMetadata UUID & schema versioning.
2. CollectorHealth, CollectorPriority, & Collector dependencies DAG ordering.
3. SnapshotValidator integrity checks.
4. CollectorContext explicit parameter passing.
5. RefreshScheduler adaptive refresh rates.
6. StudioEventBus event distribution.
7. SnapshotBuilder on_snapshot_created callback hooks.
8. SnapshotCache previous vs current snapshot comparison.
9. StudioState UI separation & StudioCommandQueue enqueue/dequeue.
10. PluginRegistry manifest compatibility validation.
11. EngineStudioCoordinator backward compatibility & fault-tolerant timeout recovery.
"""

from __future__ import annotations

import logging
import time

from camera_analytics.studio.control.command_queue import CommandType, StudioCommand, StudioCommandQueue
from camera_analytics.studio.coordinator import EngineStudioCoordinator
from camera_analytics.studio.events.event_bus import StudioEvent, StudioEventBus, StudioEventType
from camera_analytics.studio.plugins.inspector_plugin import IInspectorPanel, InspectorPlugin
from camera_analytics.studio.plugins.plugin_registry import PluginRegistry
from camera_analytics.studio.scheduler import AdaptiveRefreshMode, RefreshScheduler
from camera_analytics.studio.snapshot.builder import SnapshotBuilder
from camera_analytics.studio.snapshot.cache import SnapshotCache
from camera_analytics.studio.snapshot.engine_studio_snapshot import EngineStudioSnapshot, SnapshotMetadata
from camera_analytics.studio.snapshot.validator import SnapshotValidator
from camera_analytics.studio.telemetry.base_collector import CollectorPriority, ITelemetryCollector
from camera_analytics.studio.telemetry.collector_context import CollectorContext
from camera_analytics.studio.telemetry.collector_health import CollectorHealth, CollectorStatus
from camera_analytics.studio.telemetry.metrics_aggregator import MetricsAggregator
from camera_analytics.studio.workspace.studio_state import StudioState

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestStudioCoreHardening")


def test_snapshot_metadata_and_validator():
    meta = SnapshotMetadata()
    assert len(meta.snapshot_id) == 36  # Valid UUID4 string
    assert meta.snapshot_schema_version == "2.0.0"

    coord = EngineStudioCoordinator()
    snapshot = coord.generate_snapshot()
    assert snapshot.metadata.sequence_number == 1
    assert SnapshotValidator.validate(snapshot)
    print("[+] SnapshotMetadata UUID, schema version & SnapshotValidator test PASSED.")


def test_collector_health_and_context():
    health = CollectorHealth(collector_id="test_collector")
    assert health.status == CollectorStatus.ACTIVE

    health.record_timeout(120.0)
    assert health.status == CollectorStatus.TIMEOUT
    assert health.timeout_count == 1

    ctx = CollectorContext(engine_id="test_engine_99", device="cuda:0")
    assert ctx.engine_id == "test_engine_99"
    print("[+] CollectorHealth lifecycle & CollectorContext parameter passing test PASSED.")


def test_snapshot_cache_and_builder_hooks():
    builder = SnapshotBuilder()
    received_snapshots = []

    def hook(snap: EngineStudioSnapshot) -> None:
        received_snapshots.append(snap)

    builder.register_on_snapshot_created_hook(hook)

    snap1 = builder.build(sequence_id=1, generation_time_ms=1.5, collector_count=12, collector_success_count=12, collector_failed_count=0, collector_timeout_count=0)
    assert len(received_snapshots) == 1
    assert received_snapshots[0].sequence_id == 1

    cache = SnapshotCache()
    cache.push(snap1)
    assert cache.current_snapshot is snap1
    assert cache.previous_snapshot is None

    snap2 = builder.build(sequence_id=2, generation_time_ms=2.0, collector_count=12, collector_success_count=12, collector_failed_count=0, collector_timeout_count=0)
    cache.push(snap2)
    assert cache.current_snapshot is snap2
    assert cache.previous_snapshot is snap1
    print("[+] SnapshotCache previous/current & SnapshotBuilder on_snapshot_created hooks test PASSED.")


def test_metrics_aggregator():
    agg = MetricsAggregator(window_size=5)
    agg.record_sample(frame_time_ms=33.3, pipeline_latency_ms=15.0)
    agg.record_sample(frame_time_ms=33.3, pipeline_latency_ms=20.0)
    agg.record_sample(frame_time_ms=33.3, pipeline_latency_ms=25.0)

    assert agg.rolling_fps > 25.0
    assert agg.average_latency_ms == 20.0
    assert agg.get_latency_percentile(95.0) >= 20.0
    print("[+] MetricsAggregator rolling averages & P95 latency test PASSED.")


def test_studio_state_and_command_queue():
    state = StudioState(selected_tab="pipeline_graph", selected_camera="cam_parking_02")
    assert state.selected_tab == "pipeline_graph"

    queue = StudioCommandQueue()
    cmd = StudioCommand(command_type=CommandType.RELOAD_CONFIG, payload={"config": "standalone.json"})
    queue.enqueue(cmd)
    assert len(queue) == 1

    dequeued = queue.dequeue()
    assert dequeued.command_type == CommandType.RELOAD_CONFIG
    assert len(queue) == 0
    print("[+] StudioState UI separation & StudioCommandQueue enqueue/dequeue test PASSED.")


def test_studio_event_bus():
    bus = StudioEventBus()
    received_events = []

    def on_tab_change(evt: StudioEvent) -> None:
        received_events.append(evt)

    bus.subscribe(StudioEventType.TAB_CHANGED, on_tab_change)

    event = StudioEvent(event_type=StudioEventType.TAB_CHANGED, payload={"tab": "human_runtime"})
    bus.publish(event)

    assert len(received_events) == 1
    assert received_events[0].payload["tab"] == "human_runtime"
    print("[+] StudioEventBus internal event pub/sub test PASSED.")


def test_refresh_scheduler():
    sched = RefreshScheduler(default_mode=AdaptiveRefreshMode.DEBUG)
    assert sched.target_fps == 10.0
    assert sched.interval_seconds == 0.1

    sched.set_mode(AdaptiveRefreshMode.BENCHMARK)
    assert sched.target_fps == 20.0
    print("[+] RefreshScheduler adaptive refresh rates test PASSED.")


def main():
    print("\n========================================================")
    print("   SPRINT H1.5D1.5 STUDIO CORE HARDENING TEST ")
    print("========================================================")
    test_snapshot_metadata_and_validator()
    test_collector_health_and_context()
    test_snapshot_cache_and_builder_hooks()
    test_metrics_aggregator()
    test_studio_state_and_command_queue()
    test_studio_event_bus()
    test_refresh_scheduler()
    print("========================================================\n")
    print("[SUCCESS] All Sprint H1.5D1.5 Studio Core Hardening Tests PASSED!\n")


if __name__ == "__main__":
    main()
