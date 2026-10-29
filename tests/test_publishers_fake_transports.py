"""
Unit tests for Slice 1 Messaging fixes:
- Faked RabbitMQPublisher (publish & publish_raw, success & error metric updates)
- Faked MQTTPublisher (publish & publish_raw, topic formatting, error metric updates)
- Faked RestPublisher (publish & publish_raw, timeout & error metric updates)
- LogPublisher heartbeat deduplication bypass (identical heartbeats delivered twice)
- EventPublisher.flush() default no-op & LogPublisher flush
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from camera_analytics.communication.models import StandardAnalyticsEvent
from camera_analytics.communication.publisher_base import EventPublisher
from camera_analytics.communication.publishers.log_publisher import LogPublisher
from camera_analytics.communication.publishers.mqtt_publisher import MQTTPublisher
from camera_analytics.communication.publishers.rabbitmq_publisher import RabbitMQPublisher
from camera_analytics.communication.publishers.rest_publisher import RestPublisher


class TestMessagingSlice1(unittest.TestCase):
    """Test suite covering Slice 1 messaging fixes with in-memory fakes/mocks."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.sample_event = StandardAnalyticsEvent(
            event_type="TEST_EVENT",
            message="Slice 1 test",
            camera_id="cam_01",
        )
        self.sample_json = json.dumps(self.sample_event.to_dict())

    def tearDown(self) -> None:
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # 1. RabbitMQ with Fake Pika
    # -------------------------------------------------------------------------

    def test_rabbitmq_fake_pika_success(self) -> None:
        """Test RabbitMQPublisher with faked pika connection & channel."""
        fake_pika = MagicMock()
        fake_conn = MagicMock()
        fake_channel = MagicMock()
        fake_channel.is_open = True
        fake_conn.is_open = True
        fake_pika.BlockingConnection.return_value = fake_conn
        fake_conn.channel.return_value = fake_channel

        pub = RabbitMQPublisher(name="fake_rmq")
        pub.initialize({})

        # Inject fake pika before start
        with patch.dict("sys.modules", {"pika": fake_pika}):
            pub.on_start()

        self.assertTrue(pub._is_healthy)
        self.assertIsNotNone(pub._channel)

        # Test publish() success
        pub._is_running = True
        ok = pub.publish(self.sample_event, self.sample_json)
        self.assertTrue(ok)
        self.assertEqual(pub.metrics.published_count, 1)
        self.assertEqual(pub.metrics.failed_count, 0)
        fake_channel.basic_publish.assert_called_once()

        # Test publish_raw() success
        hb = {"instance_id": "eng_1", "seq": 1}
        ok_raw = pub.publish_raw("cctv.engine.heartbeat", "engine.heartbeat.eng_1", hb)
        self.assertTrue(ok_raw)
        self.assertEqual(pub.metrics.published_count, 2)
        self.assertEqual(pub.metrics.failed_count, 0)

    def test_rabbitmq_fake_pika_failure_metrics(self) -> None:
        """Test RabbitMQPublisher error handling when basic_publish throws."""
        fake_pika = MagicMock()
        fake_conn = MagicMock()
        fake_channel = MagicMock()
        fake_channel.is_open = True
        fake_conn.is_open = True
        fake_channel.basic_publish.side_effect = RuntimeError("AMQP socket write error")
        fake_pika.BlockingConnection.return_value = fake_conn
        fake_conn.channel.return_value = fake_channel

        pub = RabbitMQPublisher(name="fake_rmq_fail")
        pub.initialize({})

        with patch.dict("sys.modules", {"pika": fake_pika}):
            pub.on_start()

        pub._is_running = True
        ok = pub.publish(self.sample_event, self.sample_json)
        self.assertFalse(ok)
        self.assertEqual(pub.metrics.published_count, 0)
        self.assertGreater(pub.metrics.failed_count, 0)
        self.assertIn("socket write error", pub.metrics.last_error)

    # -------------------------------------------------------------------------
    # 2. MQTT with Fake Paho
    # -------------------------------------------------------------------------

    def test_mqtt_fake_paho_success(self) -> None:
        """Test MQTTPublisher publish and on_publish_raw with faked paho client."""
        fake_paho = MagicMock()
        fake_paho.MQTT_ERR_SUCCESS = 0
        fake_client = MagicMock()
        info_mock = MagicMock()
        info_mock.rc = 0
        fake_client.publish.return_value = info_mock
        fake_paho.Client.return_value = fake_client

        pub = MQTTPublisher(name="fake_mqtt", raw_topic="cctv/telemetry/{routing_key}")
        pub.initialize({})
        pub._paho = fake_paho
        pub._client = fake_client
        pub._is_running = True
        pub._is_connected = True

        # Test publish() for discrete events
        ok = pub.publish(self.sample_event, self.sample_json)
        self.assertTrue(ok)
        self.assertEqual(pub.metrics.published_count, 1)
        self.assertEqual(pub.metrics.failed_count, 0)
        fake_client.publish.assert_called_with(
            topic="camera/cam_01/analytics/events",
            payload=self.sample_json,
            qos=1,
            retain=False,
        )

        # Test on_publish_raw() for heartbeats without touching event.camera_id
        hb = {"instance_id": "eng_1", "seq": 1}
        ok_raw = pub.publish_raw("cctv.engine.heartbeat", "heartbeat.eng_1", hb)
        self.assertTrue(ok_raw)
        self.assertEqual(pub.metrics.published_count, 2)
        fake_client.publish.assert_called_with(
            topic="cctv/telemetry/heartbeat.eng_1",
            payload=json.dumps(hb, separators=(",", ":")),
            qos=1,
            retain=False,
        )

    def test_mqtt_publish_raw_error_metrics(self) -> None:
        """Test MQTTPublisher failure path updates metrics."""
        fake_paho = MagicMock()
        fake_paho.MQTT_ERR_SUCCESS = 0
        fake_client = MagicMock()
        info_mock = MagicMock()
        info_mock.rc = 1  # Not success
        fake_client.publish.return_value = info_mock
        fake_paho.Client.return_value = fake_client

        pub = MQTTPublisher(name="fake_mqtt_err")
        pub.initialize({})
        pub._paho = fake_paho
        pub._client = fake_client
        pub._is_running = True
        pub._is_connected = True

        ok = pub.publish_raw("cctv.engine.heartbeat", "heartbeat.eng_1", {"instance_id": "eng_1"})
        self.assertFalse(ok)
        self.assertEqual(pub.metrics.published_count, 0)
        self.assertEqual(pub.metrics.failed_count, 1)
        self.assertIn("rc=1", pub.metrics.last_error)

    # -------------------------------------------------------------------------
    # 3. REST with Fake Urllib
    # -------------------------------------------------------------------------

    def test_rest_fake_urllib_success(self) -> None:
        """Test RestPublisher publish and on_publish_raw with mocked urlopen."""
        pub = RestPublisher(name="fake_rest", endpoint_url="http://fake.local/events", raw_endpoint_url="http://fake.local/raw")
        pub.initialize({})
        pub.start()

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
            ok = pub.publish(self.sample_event, self.sample_json)
            self.assertTrue(ok)
            self.assertEqual(pub.metrics.published_count, 1)
            self.assertEqual(pub.metrics.failed_count, 0)

            # Check request URL
            sent_req = mock_urlopen.call_args[0][0]
            self.assertEqual(sent_req.full_url, "http://fake.local/events")

        # Test on_publish_raw
        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
            hb = {"instance_id": "eng_1", "seq": 1}
            ok_raw = pub.publish_raw("cctv.engine.heartbeat", "engine.heartbeat", hb)
            self.assertTrue(ok_raw)
            self.assertEqual(pub.metrics.published_count, 2)
            sent_req = mock_urlopen.call_args[0][0]
            self.assertEqual(sent_req.full_url, "http://fake.local/raw")

    def test_rest_fake_urllib_failure_metrics(self) -> None:
        """Test RestPublisher failure updates metrics."""
        pub = RestPublisher(name="fake_rest_fail", endpoint_url="http://fake.local/events", timeout_sec=0.01, max_retries=0)
        pub.initialize({})
        pub.start()

        with patch("urllib.request.urlopen", side_effect=Exception("HTTP connection refused")):
            ok = pub.publish(self.sample_event, self.sample_json)
            self.assertFalse(ok)
            self.assertEqual(pub.metrics.published_count, 0)
            self.assertGreater(pub.metrics.failed_count, 0)
            self.assertIn("connection refused", pub.metrics.last_error)

    # -------------------------------------------------------------------------
    # 4. LogPublisher Heartbeat Deduplication Bypass
    # -------------------------------------------------------------------------

    def test_log_publisher_heartbeat_delivered_twice(self) -> None:
        """Test that sending identical heartbeat payloads twice is delivered twice."""
        log_pub = LogPublisher(name="log_hb_test", log_dir=self.temp_dir, ignore_change_detection=False)
        log_pub.initialize({"log_dir": self.temp_dir})
        log_pub.start()

        hb1 = {"instance_id": "e1", "seq": 1, "cpu": 10.0}
        hb2 = {"instance_id": "e1", "seq": 2, "cpu": 10.0}

        r1 = log_pub.publish_raw("cctv.engine.heartbeat", "engine.heartbeat.e1", hb1)
        r2 = log_pub.publish_raw("cctv.engine.heartbeat", "engine.heartbeat.e1", hb2)

        self.assertTrue(r1, "Heartbeat 1 was rejected")
        self.assertTrue(r2, "Heartbeat 2 was wrongly suppressed by change detection!")

        log_pub.flush()
        log_pub.stop()

        ndjson_path = os.path.join(self.temp_dir, "analytics.ndjson")
        self.assertTrue(os.path.exists(ndjson_path))
        with open(ndjson_path, "r", encoding="utf-8") as f:
            lines = [ln.strip() for ln in f if ln.strip()]
        self.assertEqual(len(lines), 2, f"Expected 2 lines in ndjson, got {len(lines)}")

    def test_log_publisher_snapshot_throttling_and_heartbeat_bypass(self) -> None:
        """Test snapshot change-detection and interval throttling vs heartbeat bypass."""
        import time
        sub_dir = tempfile.mkdtemp(dir=self.temp_dir)
        log_pub = LogPublisher(name="log_snap_test", log_dir=sub_dir)
        log_pub.initialize({"log_dir": sub_dir, "publish_interval_seconds": 0.1, "ignore_change_detection": False})
        log_pub.start()

        # 1. First snapshot: delivered
        snap1 = {"cameraId": "cam_01", "plugins": {"motion": {"active": False}}}
        self.assertTrue(log_pub.publish_raw("cctv.analytics", "analytics.snapshot", snap1))

        # 2. Identical snapshot twice -> suppressed by change-detection (1 delivery)
        snap1_dup = {"cameraId": "cam_01", "plugins": {"motion": {"active": False}}}
        self.assertFalse(log_pub.publish_raw("cctv.analytics", "analytics.snapshot", snap1_dup))

        # 3. Changed snapshot too soon -> throttled by publish_interval_seconds (< 0.1s)
        snap2_changed = {"cameraId": "cam_01", "plugins": {"motion": {"active": True}}}
        self.assertFalse(log_pub.publish_raw("cctv.analytics", "analytics.snapshot", snap2_changed))

        # 4. Wait for interval to elapse -> changed snapshot delivered
        time.sleep(0.12)
        self.assertTrue(log_pub.publish_raw("cctv.analytics", "analytics.snapshot", snap2_changed))

        # 5. Identical heartbeat twice -> both delivered (bypass change-detection & interval)
        hb = {"instance_id": "eng_1", "cpu": 15.0}
        self.assertTrue(log_pub.publish_raw("cctv.engine.heartbeat", "engine.heartbeat", hb))
        self.assertTrue(log_pub.publish_raw("cctv.engine.heartbeat", "engine.heartbeat", hb))

        log_pub.flush()
        log_pub.stop()

        ndjson_path = os.path.join(sub_dir, "analytics.ndjson")
        self.assertTrue(os.path.exists(ndjson_path))
        with open(ndjson_path, "r", encoding="utf-8") as f:
            lines = [ln.strip() for ln in f if ln.strip()]
        # 1 (snap1) + 1 (snap2_changed) + 2 (hb) = 4 lines
        self.assertEqual(len(lines), 4)

    # -------------------------------------------------------------------------
    # 5. EventPublisher.flush() Safety
    # -------------------------------------------------------------------------

    def test_event_publisher_flush_noop(self) -> None:
        """Test default flush() no-op on EventPublisher."""
        class DummyPublisher(EventPublisher):
            def publish(self, event, serialized):
                return True

        pub = DummyPublisher(name="dummy")
        pub.initialize({})
        pub.start()
        # Should execute cleanly without AttributeError or error
        pub.flush()
        pub.stop()


if __name__ == "__main__":
    unittest.main()
