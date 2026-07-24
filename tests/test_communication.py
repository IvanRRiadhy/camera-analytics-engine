"""
Unit tests for Event Communication Layer.

Verifies:
    - StandardAnalyticsEvent data model and AnalyticsEventSerializer JSON output.
    - PublisherRegistry registration, dynamic lookup, and instantiation.
    - LogPublisher writing JSON Lines (.jsonl) files.
    - MQTTPublisher fallback behavior and topic formatting.
    - PublisherManager broadcasting and Exception Isolation.
    - CommunicationManager non-blocking queue, worker thread, and runtime metrics.
"""

import json
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from camera_analytics.communication.manager import CommunicationManager
from camera_analytics.communication.models import (
    AnalyticsEventSerializer,
    EventSeverity,
    StandardAnalyticsEvent,
)
from camera_analytics.communication.publisher_base import EventPublisher
from camera_analytics.communication.publisher_manager import PublisherManager
from camera_analytics.communication.publishers.log_publisher import LogPublisher
from camera_analytics.communication.publishers.mqtt_publisher import MQTTPublisher
from camera_analytics.communication.registry import (
    PublisherRegistry,
    register_publisher,
)


class FaultyPublisher(EventPublisher):
    """Faulty publisher plugin designed to test Exception Isolation."""

    def __init__(self, name: str = "faulty_publisher") -> None:
        super().__init__(name=name)

    def publish(self, event: StandardAnalyticsEvent, serialized_payload: str) -> bool:
        raise RuntimeError("Simulated network crash inside FaultyPublisher.publish()")


class TestEventCommunicationLayer(unittest.TestCase):
    """Test suite for Communication Layer components."""

    def setUp(self) -> None:
        """Set up temporary directory and clear registries."""
        self.temp_dir = tempfile.mkdtemp()
        PublisherRegistry.clear()
        CommunicationManager.reset_instance()

    def tearDown(self) -> None:
        """Clean up temporary directory and reset instance."""
        CommunicationManager.reset_instance()
        PublisherRegistry.clear()
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_analytics_event_serializer(self) -> None:
        """Test StandardAnalyticsEvent model and JSON serialization consistency."""
        evt = StandardAnalyticsEvent(
            event_type="ZONE_ENTER",
            message="Track #1 entered zone 'Entrance'",
            analytics_module="TestModule",
            camera_id="cam_01",
            track_id=1,
            zone_id="entrance_zone",
            payload={"count": 5},
        )

        json_str = AnalyticsEventSerializer.serialize(evt)
        self.assertIn("ZONE_ENTER", json_str)
        self.assertIn("cam_01", json_str)

        deserialized = AnalyticsEventSerializer.deserialize(json_str)
        self.assertEqual(deserialized["event_type"], "ZONE_ENTER")
        self.assertEqual(deserialized["camera_id"], "cam_01")
        self.assertEqual(deserialized["track_id"], 1)

    def test_publisher_registry(self) -> None:
        """Test PublisherRegistry decorator registration and dynamic instantiation."""
        @register_publisher("test_pub")
        class CustomPublisher(EventPublisher):
            def publish(self, event: StandardAnalyticsEvent, serialized_payload: str) -> bool:
                return True

        self.assertTrue(PublisherRegistry.is_registered("test_pub"))
        self.assertIn("test_pub", PublisherRegistry.list_registered())

        instance = PublisherRegistry.create("test_pub")
        self.assertIsInstance(instance, CustomPublisher)
        self.assertEqual(instance.name, "test_pub")

    def test_log_publisher(self) -> None:
        """Test LogPublisher writing .jsonl files to disk."""
        log_path = Path(self.temp_dir) / "test_events.jsonl"
        pub = LogPublisher(name="log_test", log_dir=self.temp_dir, filename_pattern="test_events.jsonl", rotate_daily=False)
        pub.initialize({})
        pub.start()

        evt = StandardAnalyticsEvent(
            event_type="ZONE_EXIT",
            message="Track #2 exited zone 'Lobby'",
            analytics_module="PeopleAnalytics",
            camera_id="cam_02",
        )
        json_str = AnalyticsEventSerializer.serialize(evt)

        ok = pub.publish(evt, json_str)
        self.assertTrue(ok)
        pub.flush()
        pub.stop()

        self.assertTrue(log_path.exists())
        with open(log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            self.assertEqual(len(lines), 1)
            parsed = json.loads(lines[0])
            self.assertEqual(parsed["event_type"], "ZONE_EXIT")

    def test_mqtt_publisher_fallback(self) -> None:
        """Test MQTTPublisher fallback publishing when broker is offline."""
        mqtt_pub = MQTTPublisher(name="mqtt_test", broker="localhost", port=1883, topic="camera/{camera_id}/events")
        mqtt_pub.initialize({})
        mqtt_pub.start()

        evt = StandardAnalyticsEvent(event_type="TEST_MQTT", message="Testing MQTT", camera_id="cam_mqtt")
        json_str = AnalyticsEventSerializer.serialize(evt)

        ok = mqtt_pub.publish(evt, json_str)
        self.assertTrue(ok)
        mqtt_pub.stop()

    def test_publisher_manager_exception_isolation(self) -> None:
        """Test PublisherManager broadcasting with Exception Isolation."""
        good_pub = LogPublisher(name="good_log", log_dir=self.temp_dir, filename_pattern="good.jsonl", rotate_daily=False)
        bad_pub = FaultyPublisher(name="bad_pub")

        good_pub.initialize({})
        good_pub.start()
        bad_pub.initialize({})
        bad_pub.start()

        mgr = PublisherManager()
        mgr.register_publisher(good_pub)
        mgr.register_publisher(bad_pub)

        evt = StandardAnalyticsEvent(event_type="BROADCAST_TEST", message="Test broadcast")
        json_str = AnalyticsEventSerializer.serialize(evt)

        succ, fail = mgr.broadcast(evt, json_str)

        # Good publisher succeeds, bad publisher fails safely without crashing system
        self.assertEqual(succ, 1)
        self.assertEqual(fail, 1)

        mgr.stop()

    def test_communication_manager_worker_and_queue(self) -> None:
        """Test CommunicationManager non-blocking queue, background worker thread, and metrics."""
        log_path = Path(self.temp_dir) / "comm_events.jsonl"
        log_pub = LogPublisher(name="comm_log", log_dir=self.temp_dir, filename_pattern="comm_events.jsonl", rotate_daily=False)

        comm = CommunicationManager.get_instance(queue_size=100)
        comm.publisher_manager.register_publisher(log_pub)
        comm.initialize({})
        comm.start()

        for i in range(5):
            evt = StandardAnalyticsEvent(
                event_type="QUEUE_TEST",
                message=f"Event #{i}",
                frame_index=i,
            )
            comm.enqueue(evt)

        # Wait briefly for worker thread to process queue items
        time.sleep(0.5)

        metrics = comm.get_metrics()
        self.assertEqual(metrics.total_events, 5)
        self.assertGreaterEqual(metrics.published_events, 5)
        self.assertEqual(metrics.dropped_events, 0)

        comm.stop()
        self.assertTrue(log_path.exists())


if __name__ == "__main__":
    unittest.main()
