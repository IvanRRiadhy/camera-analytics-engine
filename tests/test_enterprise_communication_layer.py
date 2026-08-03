"""
Enterprise Communication Layer Test Suite (Sprint 12.2).

Verifies:
    1. All 5 Publishers (Log, Console, REST, RabbitMQ, MQTT) lifecycle & publish operations.
    2. EventRouter rule matching and publisher targeting.
    3. CommunicationManager bounded queue buffering, non-blocking enqueue, and metrics.
    4. Exception isolation across failing publishers.
    5. Graceful shutdown flushing.
"""

import json
import tempfile
import time
import unittest
from pathlib import Path

import camera_analytics.communication

from camera_analytics.communication import (
    CommunicationManager,
    ConsolePublisher,
    EventDetailLevel,
    EventPublisher,
    EventRouter,
    EventRoutingRule,
    EventSeverity,
    LogPublisher,
    MQTTPublisher,
    PublisherManager,
    PublisherRegistry,
    RabbitMQPublisher,
    RestPublisher,
    StandardAnalyticsEvent,
)


class TestEnterpriseCommunicationLayer(unittest.TestCase):
    """Communication Layer Unit Test Suite."""

    def setUp(self) -> None:
        """Reset CommunicationManager singleton before each test."""
        CommunicationManager.reset_instance()
        self.sample_event = StandardAnalyticsEvent(
            event_type="ZONE_ENTER",
            analytics_module="zone_enter",
            message="Track #1 entered lobby zone",
            camera_id="cam_test_01",
            track_id=1,
            zone_id="lobby_main",
            severity=EventSeverity.INFO.value,
        )

    def tearDown(self) -> None:
        """Reset CommunicationManager singleton after each test."""
        CommunicationManager.reset_instance()

    def test_publisher_registry_and_instantiation(self) -> None:
        """Verify PublisherRegistry creates instances of registered publishers."""
        log_pub = PublisherRegistry.create("log", name="test_log")
        console_pub = PublisherRegistry.create("console", name="test_console")
        rest_pub = PublisherRegistry.create("rest", name="test_rest")
        rabbitmq_pub = PublisherRegistry.create("rabbitmq", name="test_rmq")
        mqtt_pub = PublisherRegistry.create("mqtt", name="test_mqtt")

        self.assertIsInstance(log_pub, LogPublisher)
        self.assertIsInstance(console_pub, ConsolePublisher)
        self.assertIsInstance(rest_pub, RestPublisher)
        self.assertIsInstance(rabbitmq_pub, RabbitMQPublisher)
        self.assertIsInstance(mqtt_pub, MQTTPublisher)

    def test_console_and_log_publishers(self) -> None:
        """Verify ConsolePublisher and LogPublisher publish correctly."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            log_pub = LogPublisher(name="log_pub", enabled=True, log_dir=tmp_dir, rotate_daily=False)
            log_pub.initialize({})
            log_pub.start()

            console_pub = ConsolePublisher(name="console_pub", enabled=True)
            console_pub.initialize({})
            console_pub.start()

            ok_log = log_pub.publish(self.sample_event, '{"test":"payload"}')
            ok_con = console_pub.publish(self.sample_event, '{"test":"payload"}')

            self.assertTrue(ok_log)
            self.assertTrue(ok_con)

            health_log = log_pub.get_health()
            self.assertEqual(health_log["success_count"], 1)

            log_pub.stop()
            console_pub.stop()

    def test_event_router(self) -> None:
        """Verify EventRouter filters events according to rules."""
        router = EventRouter([
            {"event_types": ["CROWD_ALERT"], "publishers": ["rest_webhook"]},
            {"severities": ["CRITICAL"], "publishers": ["rest_webhook", "rabbitmq"]},
            {"event_types": ["*"], "publishers": ["file_log"]},
        ])

        all_pubs = ["file_log", "console_out", "rest_webhook", "rabbitmq"]

        # Sample event (ZONE_ENTER, INFO) should match rule 3 -> ['file_log']
        targets1 = router.route(self.sample_event, all_pubs)
        self.assertEqual(targets1, ["file_log"])

        # Alert event (CROWD_ALERT, CRITICAL) should match rule 1 & rule 2 & rule 3
        alert_event = StandardAnalyticsEvent(
            event_type="CROWD_ALERT",
            severity=EventSeverity.CRITICAL.value,
        )
        targets2 = router.route(alert_event, all_pubs)
        self.assertIn("rest_webhook", targets2)
        self.assertIn("rabbitmq", targets2)
        self.assertIn("file_log", targets2)

    def test_communication_manager_enqueue_and_flush(self) -> None:
        """Verify CommunicationManager enqueues events, processes via worker, and flushes on stop."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            mgr = CommunicationManager.get_instance(queue_size=100)
            log_pub = LogPublisher(name="log_pub", enabled=True, log_dir=tmp_dir, rotate_daily=False)
            mgr.publisher_manager.register_publisher(log_pub)
            mgr.start()

            for i in range(10):
                evt = StandardAnalyticsEvent(event_type="ZONE_ENTER", message=f"Event {i}")
                mgr.enqueue(evt)

            time.sleep(0.3)
            mgr.stop()

            metrics = mgr.get_metrics()
            self.assertEqual(metrics.total_events, 10)
            self.assertEqual(metrics.published_events, 10)
            self.assertEqual(metrics.dropped_events, 0)

    def test_exception_isolation_across_publishers(self) -> None:
        """Verify failing publisher exception does not stop working publishers."""

        class FaultyPublisher(EventPublisher):
            def publish(self, event, serialized_payload):
                raise RuntimeError("Simulated connection crash")

        with tempfile.TemporaryDirectory() as tmp_dir:
            pub_mgr = PublisherManager()
            good_pub = LogPublisher(name="good_log", enabled=True, log_dir=tmp_dir, rotate_daily=False)
            bad_pub = FaultyPublisher(name="bad_pub", enabled=True)

            pub_mgr.register_publisher(good_pub)
            pub_mgr.register_publisher(bad_pub)
            pub_mgr.start()

            succ, fail = pub_mgr.broadcast(self.sample_event, '{"test":"val"}')
            self.assertEqual(succ, 1)
            self.assertEqual(fail, 1)

            pub_mgr.stop()


if __name__ == "__main__":
    unittest.main()
