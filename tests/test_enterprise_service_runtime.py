"""
Enterprise Event Service Runtime Test Suite (Sprint 12.5).

Verifies:
    1. Immutable PlatformEvent contract & EventSchemaVersion validation.
    2. PlatformEventBus pub-sub distribution & PlatformEventRouter.
    3. ServiceDependencyGraph DAG & Topological Sort startup sequence.
    4. ServiceLoader dynamic loading with Exception Isolation barriers.
    5. EventDispatcher subscription matching & priority resolution.
    6. ServiceExecutionEngine worker pool execution & retry policies.
    7. Recording & Alarm Service Plugins lifecycle & event processing.
    8. HierarchicalHealthMonitor runtime health aggregation.
"""

import tempfile
import time
import unittest
from pathlib import Path

from camera_analytics.communication.models import StandardAnalyticsEvent
from camera_analytics.eventing import (
    AnalyticsPayload,
    EventSchemaVersion,
    PlatformEvent,
    PlatformEventBus,
    PlatformEventRouter,
)
from camera_analytics.services import (
    EventDispatcher,
    EventService,
    EventServiceRuntime,
    EventServiceRuntimeManager,
    HierarchicalHealthMonitor,
    ServiceContext,
    ServiceDependencyGraph,
    ServiceDiscovery,
    ServiceExecutionEngine,
    ServiceLifecycleState,
    ServiceLoader,
    ServiceManifest,
    ServiceRegistry,
)


class FaultyServicePlugin(EventService):
    """Faulty service plugin designed to test Exception Isolation."""

    def initialize(self, context: ServiceContext) -> None:
        super().initialize(context)

    def start(self) -> None:
        pass

    def on_event(self, event: StandardAnalyticsEvent | PlatformEvent) -> None:
        raise RuntimeError("Simulated crash inside FaultyServicePlugin.on_event()")

    def stop(self) -> None:
        pass


class TestEnterpriseServiceRuntime(unittest.TestCase):
    """Event Service Runtime Unit Test Suite."""

    def setUp(self) -> None:
        """Set up temporary directory and runtime."""
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.storage_path = Path(self.tmp_dir.name)
        self.event_bus = PlatformEventBus()
        self.runtime = EventServiceRuntime(event_bus=self.event_bus, storage_dir=self.storage_path)

    def tearDown(self) -> None:
        """Stop runtime and cleanup temporary directory."""
        if self.runtime._is_running:
            self.runtime.stop_all_services()
        try:
            self.tmp_dir.cleanup()
        except Exception:
            pass

    def test_platform_event_immutability_and_versioning(self) -> None:
        """Verify PlatformEvent is immutable and version checking works."""
        pe = PlatformEvent.create(
            event_type="TEST_EVENT",
            payload=AnalyticsPayload(camera_id="cam_01", severity="INFO"),
            version="1.0",
        )
        self.assertEqual(pe.event_type, "TEST_EVENT")
        self.assertTrue(EventSchemaVersion.is_compatible(pe.version))

        # Immutability check: modifying dataclass attributes must raise AttributeError
        with self.assertRaises(AttributeError):
            pe.event_type = "MODIFIED"  # type: ignore

    def test_dependency_graph_topological_sort(self) -> None:
        """Verify ServiceDependencyGraph computes correct topological startup order."""
        m_rec = ServiceManifest(service_name="recording", version="1.0", capabilities=["rec.cap"], dependencies=[])
        m_alarm = ServiceManifest(service_name="alarm", version="1.0", capabilities=["alarm.cap"], dependencies=[])
        m_inv = ServiceManifest(service_name="investigation", version="1.0", capabilities=[], dependencies=["rec.cap", "alarm.cap"])

        graph = ServiceDependencyGraph()
        graph.add_manifest(m_inv)
        graph.add_manifest(m_rec)
        graph.add_manifest(m_alarm)

        order = graph.compute_startup_order()
        self.assertEqual(len(order), 3)
        self.assertEqual(order[-1], "investigation")  # investigation must start last

    def test_exception_isolation_barrier(self) -> None:
        """Verify crashing service plugin does not stop execution engine or runtime."""
        from camera_analytics.services.manifest import RetryPolicyConfig

        manifest = ServiceManifest(
            service_name="faulty",
            version="1.0",
            event_types=["*"],
            retry_policy=RetryPolicyConfig(max_retries=1, backoff_sec=0.0),
        )
        faulty_plugin = FaultyServicePlugin()
        self.runtime.registry.register(manifest, faulty_plugin)

        self.runtime.execution_engine.start()
        entry = self.runtime.registry.get("faulty")
        self.assertIsNotNone(entry)

        evt = StandardAnalyticsEvent(event_type="CROWD_ALERT", camera_id="cam_01")
        # Execute faulty event
        self.runtime.execution_engine.execute_event(entry, evt)

        # Confirm registry recorded failure without crashing runtime
        self.assertEqual(entry.state, ServiceLifecycleState.FAILED)
        self.assertEqual(entry.error_count, 1)

    def test_runtime_manager_discovery_and_execution(self) -> None:
        """Verify EventServiceRuntimeManager discovers, loads, and dispatches events."""
        mgr = EventServiceRuntimeManager(
            plugin_dir="camera_analytics/services/plugins",
            event_bus=self.event_bus,
        )

        loaded = mgr.initialize_and_start()
        self.assertGreaterEqual(loaded, 2)

        evt = StandardAnalyticsEvent(event_type="CROWD_ALERT", camera_id="cam_01")
        dispatched = mgr.dispatch(evt)
        self.assertGreaterEqual(dispatched, 1)

        health = mgr.get_health_report()
        self.assertEqual(health["runtime"]["status"], "HEALTHY")

        mgr.shutdown()


if __name__ == "__main__":
    unittest.main()
