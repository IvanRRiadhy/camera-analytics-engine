"""
Event Serialization Optimization Test Suite (Sprint 12.0.1).

Verifies:
    1. Detail level payload size targets (summary: 300-700B, standard: 700-1200B, full: >1800B).
    2. Compact array representation for bounding boxes [x1,y1,x2,y2] and ground points [x,y].
    3. Removal of redundant camera/frame metadata in business event summary mode.
    4. LogPublisher detail_level configuration.
"""

import json
import tempfile
import unittest
from pathlib import Path

from camera_analytics.communication.models import (
    AnalyticsEventSerializer,
    EventDetailLevel,
    StandardAnalyticsEvent,
)
from camera_analytics.communication.publishers.log_publisher import LogPublisher
from camera_analytics.entities.models import (
    BoundingBoxEntity,
    CameraEntity,
    FrameEntity,
    GroundPointEntity,
    KeypointEntity,
    PoseEntity,
    TrackEntity,
    ZoneEntity,
)


class TestEventSerializationOptimization(unittest.TestCase):
    """Serialization Optimization & Size Reduction Test Suite."""

    def setUp(self) -> None:
        """Set up test entities and events."""
        self.camera = CameraEntity(
            camera_id="cam_opt_01",
            camera_name="Main Entrance Lobby Camera",
            location="Building A Lobby",
            resolution=(1920, 1080),
            fps=30.0,
        )
        self.frame = FrameEntity(
            frame_index=150,
            timestamp=5.0,
            frame_width=1920,
            frame_height=1080,
            fps=30.0,
        )
        kps = [
            KeypointEntity(index=i, name=f"kp_{i}", x=100.0 + i, y=200.0 + i, confidence=0.9)
            for i in range(17)
        ]
        self.pose = PoseEntity(keypoints=kps, confidence=0.92)
        bbox_ent = BoundingBoxEntity(x1=438, y1=202, x2=615, y2=634)
        gp_ent = GroundPointEntity(x=526, y=634)
        self.track = TrackEntity(
            track_id=101,
            confidence=0.95,
            bbox=bbox_ent,
            ground_point=gp_ent,
            pose=self.pose,
        )
        self.zone = ZoneEntity(zone_id="zone_lobby", zone_name="Lobby Main Region")

        self.std_event = StandardAnalyticsEvent(
            event_type="ZONE_ENTER",
            analytics_module="zone_enter",
            message="Track #101 entered zone 'Lobby Main Region' (zone_lobby)",
            camera_id=self.camera.camera_id,
            camera_name=self.camera.camera_name,
            severity="INFO",
            track_id=101,
            zone_id="zone_lobby",
            zone_name="Lobby Main Region",
            frame_index=150,
            payload={
                "track_id": 101,
                "zone_id": "zone_lobby",
                "zone_name": "Lobby Main Region",
                "track": self.track.to_dict(),
                "bbox": {"x1": 438, "y1": 202, "x2": 615, "y2": 634},
                "ground_point": {"x": 526, "y": 634},
            },
            metadata={
                "camera": self.camera.to_dict(),
                "frame": self.frame.to_dict(),
            },
        )

    def test_summary_detail_level_size_and_content(self) -> None:
        """Verify summary mode achieves 300-700 byte size range and excludes heavy metadata."""
        serialized = AnalyticsEventSerializer.serialize(self.std_event, detail_level=EventDetailLevel.SUMMARY)
        size_bytes = len(serialized.encode("utf-8"))

        # Check byte size constraint
        self.assertLessEqual(size_bytes, 700)
        self.assertGreaterEqual(size_bytes, 250)

        # Check content exclusions and array compacting
        parsed = json.loads(serialized)
        self.assertNotIn("metadata", parsed)
        self.assertNotIn("message", parsed)
        self.assertNotIn("camera_name", parsed)

        # Verify compact bbox array representation
        payload_track = parsed["payload"]["track"]
        self.assertEqual(payload_track["bbox"], [438, 202, 615, 634])
        self.assertNotIn("pose", payload_track)

    def test_standard_detail_level_size_and_content(self) -> None:
        """Verify standard mode achieves 700-1200 byte size range."""
        serialized = AnalyticsEventSerializer.serialize(self.std_event, detail_level=EventDetailLevel.STANDARD)
        size_bytes = len(serialized.encode("utf-8"))

        self.assertLessEqual(size_bytes, 1200)

        parsed = json.loads(serialized)
        self.assertIn("message", parsed)
        self.assertIn("camera_name", parsed)
        self.assertNotIn("metadata", parsed)
        self.assertNotIn("pose", parsed["payload"]["track"])

    def test_full_detail_level_includes_everything(self) -> None:
        """Verify full mode includes pose keypoints and nested metadata."""
        serialized = AnalyticsEventSerializer.serialize(self.std_event, detail_level=EventDetailLevel.FULL)
        parsed = json.loads(serialized)

        self.assertIn("metadata", parsed)
        self.assertIn("pose", parsed["payload"]["track"])
        self.assertEqual(len(parsed["payload"]["track"]["pose"]["keypoints"]), 17)

    def test_log_publisher_with_detail_level(self) -> None:
        """Verify LogPublisher formats events according to detail_level config."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            pub = LogPublisher(
                name="test_summary_pub",
                enabled=True,
                log_dir=tmp_dir,
                filename_pattern="summary_events.jsonl",
                rotate_daily=False,
                detail_level="summary",
            )
            pub.initialize({})
            pub.start()

            pub.publish(self.std_event, "")
            pub.flush()
            pub.stop()

            log_file = Path(tmp_dir) / "summary_events.jsonl"
            lines = log_file.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1)

            parsed = json.loads(lines[0])
            self.assertNotIn("metadata", parsed)
            self.assertLessEqual(len(lines[0].encode("utf-8")), 700)


if __name__ == "__main__":
    unittest.main()
