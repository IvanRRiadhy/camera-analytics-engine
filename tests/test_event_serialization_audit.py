"""
Event Serialization Audit and Validation Test Suite.

Verifies:
    1. Complete event data propagation (no unintended null values).
    2. Strict NDJSON (JSON Lines) format compliance (one valid JSON object per line, UTF-8 preserved).
    3. Bidirectional serialization & deserialization fidelity.
    4. Payload self-containment for enterprise analytics events.
"""

import json
import tempfile
import unittest
from pathlib import Path

from camera_analytics.communication.models import AnalyticsEventSerializer, StandardAnalyticsEvent
from camera_analytics.communication.publishers.log_publisher import LogPublisher
from camera_analytics.entities.models import CameraEntity, FrameEntity, ZoneEntity
from camera_analytics.entities.serializer import EntitySerializer
from camera_analytics.plugins.zone_occupancy.module import ZoneOccupancyModule
from camera_analytics.scene.models import Scene, SceneMetadata


class TestEventSerializationAudit(unittest.TestCase):
    """Serialization Audit & NDJSON Format Test Suite."""

    def setUp(self) -> None:
        """Set up test environment."""
        self.camera = CameraEntity(camera_id="cam_audit", camera_name="Entrance Cam", resolution=(1920, 1080), fps=30.0)
        self.frame = FrameEntity(frame_index=100, timestamp=100.5, frame_width=1920, frame_height=1080, fps=30.0)
        self.zone = ZoneEntity(zone_id="zone_lobby", zone_name="Lobby Main Region")

        self.std_event = StandardAnalyticsEvent(
            event_type="ZONE_OCCUPANCY",
            message="Zone 'Lobby Main Region' (zone_lobby) occupancy updated: 5 person(s)",
            analytics_module="zone_occupancy",
            camera_id="cam_audit",
            camera_name="Entrance Cam",
            severity="WARNING",
            track_id=42,
            zone_id="zone_lobby",
            zone_name="Lobby Main Region",
            frame_index=100,
            payload={
                "zone_id": "zone_lobby",
                "zone_name": "Lobby Main Region",
                "occupancy_count": 5,
                "active_track_ids": [42, 43, 44, 45, 46],
                "threshold": 5,
                "threshold_exceeded": True,
            },
            metadata={
                "camera": self.camera.to_dict(),
                "frame": self.frame.to_dict(),
            },
        )

    def test_complete_event_data_population(self) -> None:
        """Verify no essential event fields are null when derived from context."""
        evt = EntitySerializer.build_analytics_event(
            event_type="ZONE_ENTER",
            message="Track #42 entered zone 'Lobby Main Region'",
            analytics_module="zone_enter",
            camera=self.camera,
            frame=self.frame,
            zone=self.zone,
            track_id=42,
            payload={"custom_metric": 12.34},
        )
        d = evt.to_dict()

        self.assertEqual(d["camera_id"], "cam_audit")
        self.assertEqual(d["camera_name"], "Entrance Cam")
        self.assertEqual(d["track_id"], 42)
        self.assertEqual(d["zone_id"], "zone_lobby")
        self.assertEqual(d["zone_name"], "Lobby Main Region")
        self.assertEqual(d["frame_index"], 100)
        self.assertIsNotNone(d["correlation_id"])

        # Metadata camera checks
        cam_meta = d["metadata"].get("camera")
        self.assertIsNotNone(cam_meta)
        self.assertEqual(cam_meta["resolution"], [1920, 1080])
        self.assertEqual(cam_meta["fps"], 30.0)

    def test_bidirectional_serialization(self) -> None:
        """Verify event serialization and deserialization fidelity."""
        json_str = AnalyticsEventSerializer.serialize(self.std_event)

        # Must be single line (NDJSON requirement)
        self.assertNotIn("\n", json_str)

        # Deserialize back
        data = AnalyticsEventSerializer.deserialize(json_str)

        self.assertEqual(data["event_id"], self.std_event.event_id)
        self.assertEqual(data["schema_version"], "1.0")
        self.assertEqual(data["event_type"], "ZONE_OCCUPANCY")
        self.assertEqual(data["severity"], "WARNING")
        self.assertEqual(data["zone_id"], "zone_lobby")
        self.assertEqual(data["zone_name"], "Lobby Main Region")
        self.assertEqual(data["payload"]["occupancy_count"], 5)

    def test_ndjson_log_publisher_validity(self) -> None:
        """Verify LogPublisher generates valid NDJSON (JSON Lines) files."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            pub = LogPublisher(
                name="test_log_pub",
                enabled=True,
                log_dir=tmp_dir,
                filename_pattern="test_events.jsonl",
                rotate_daily=False,
                detail_level="standard",
            )
            pub.initialize({})
            pub.start()

            # Write 5 events
            for i in range(5):
                evt = StandardAnalyticsEvent(
                    event_type=f"EVENT_{i}",
                    message=f"Event message {i} with UTF-8 chars: 🔥 人員檢測",
                    analytics_module="test_module",
                    camera_id="cam_audit",
                    frame_index=i,
                )
                payload_str = AnalyticsEventSerializer.serialize(evt)
                pub.publish(evt, payload_str)

            pub.flush()
            pub.stop()

            # Inspect written file
            log_file = Path(tmp_dir) / "test_events.jsonl"
            self.assertTrue(log_file.exists())

            lines = log_file.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 5)

            # Each line must be a valid JSON object
            for idx, line in enumerate(lines):
                parsed = json.loads(line)
                self.assertEqual(parsed["event_type"], f"EVENT_{idx}")
                self.assertIn("人員檢測", parsed["message"])


if __name__ == "__main__":
    unittest.main()
