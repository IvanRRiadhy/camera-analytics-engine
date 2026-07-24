"""
Unit tests for Domain Entity Model & Payload SDK.

Verifies:
    - BoundingBoxEntity, GroundPointEntity, VelocityEntity, and DirectionEntity calculations.
    - AnalyticsPayload SDK builders and custom domain namespace extension.
    - EntityFactory creation of TrackEntity, CameraEntity, FrameEntity, and ZoneEntity from runtime models.
    - EntitySerializer event construction and JSON serialization.
"""

import json
import unittest

from camera_analytics.entities.factory import EntityFactory
from camera_analytics.entities.models import (
    BoundingBoxEntity,
    CameraEntity,
    DirectionEntity,
    FrameEntity,
    GroundPointEntity,
    GroundPointSource,
    PoseEntity,
    TrackEntity,
    VelocityEntity,
    ZoneEntity,
    ZoneState,
)
from camera_analytics.entities.payload import AnalyticsPayload
from camera_analytics.entities.serializer import EntitySerializer
from camera_analytics.models import (
    BoundingBox,
    Camera,
    Detection,
    DetectionClass,
    Point,
    Track,
    Zone,
    ZoneType,
)


class TestDomainEntityModel(unittest.TestCase):
    """Test suite for Domain Entity Model & Payload SDK components."""

    def test_bounding_box_entity(self) -> None:
        """Test BoundingBoxEntity center, area, width, height calculations."""
        bbox = BoundingBoxEntity(x1=100, y1=200, x2=500, y2=800)
        self.assertEqual(bbox.width, 400)
        self.assertEqual(bbox.height, 600)
        self.assertEqual(bbox.area, 240000)
        self.assertEqual(bbox.center, (300, 500))

        d = bbox.to_dict()
        self.assertEqual(d["width"], 400)
        self.assertEqual(d["center_x"], 300)

    def test_velocity_and_direction_entity(self) -> None:
        """Test VelocityEntity speed and DirectionEntity cardinal direction calculation."""
        vel = VelocityEntity(vx=3.0, vy=4.0)
        self.assertEqual(vel.speed, 5.0)

        dir_ent = DirectionEntity(heading_degrees=90.0, cardinal_direction="S")
        self.assertEqual(dir_ent.cardinal_direction, "S")

    def test_analytics_payload_sdk_builder(self) -> None:
        """Test AnalyticsPayload strongly typed properties and custom namespace extensions."""
        payload = AnalyticsPayload()
        payload.people.count = 4
        payload.people.active_track_ids = [1, 2, 3, 4]

        payload.loitering.loitering_count = 1
        payload.loitering.warning_track_ids = [2]

        payload.custom["forklift"] = {"status": "ACTIVE", "speed": 12.5}

        d = payload.to_dict()

        self.assertIn("people", d)
        self.assertEqual(d["people"]["count"], 4)
        self.assertIn("loitering", d)
        self.assertEqual(d["loitering"]["loitering_count"], 1)
        self.assertIn("forklift", d)
        self.assertEqual(d["forklift"]["speed"], 12.5)

    def test_entity_factory(self) -> None:
        """Test EntityFactory manufacturing TrackEntity, CameraEntity, and ZoneEntity from runtime objects."""
        # 1. Test CameraEntity Factory
        cam = Camera("cam_test_01", "Lobby Camera", "rtsp://192.168.1.100/live")
        cam_ent = EntityFactory.create_camera_entity(cam)
        self.assertEqual(cam_ent.camera_id, "cam_test_01")
        self.assertEqual(cam_ent.camera_name, "Lobby Camera")

        # 2. Test ZoneEntity Factory
        zone = Zone(
            zone_id="z1",
            name="Main Door",
            zone_type=ZoneType.REGION,
            points=[Point(0, 0), Point(100, 0), Point(100, 100), Point(0, 100)],
        )
        zone_ent = EntityFactory.create_zone_entity(zone, current_state=ZoneState.ENTER, dwell_frames=5)
        self.assertEqual(zone_ent.zone_id, "z1")
        self.assertEqual(zone_ent.current_state, ZoneState.ENTER)

        # 3. Test TrackEntity Factory
        det = Detection(bbox=BoundingBox(10, 20, 110, 220), confidence=0.95, detection_class=DetectionClass.PERSON)
        track = Track(track_id=10, detection=det, first_frame=1, last_frame=1)
        track_ent = EntityFactory.create_track_entity(track)

        self.assertEqual(track_ent.track_id, 10)
        self.assertEqual(track_ent.confidence, 0.95)
        self.assertIsNotNone(track_ent.bbox)
        self.assertEqual(track_ent.bbox.width, 100)

    def test_entity_serializer(self) -> None:
        """Test EntitySerializer event construction and JSON string generation."""
        cam_ent = CameraEntity(camera_id="cam_01", camera_name="Entrance Cam")
        frame_ent = FrameEntity(frame_index=15, timestamp=1.5, frame_width=1920, frame_height=1080)
        zone_ent = ZoneEntity(zone_id="z_door", zone_name="Doorway", current_state=ZoneState.ENTER)

        payload = AnalyticsPayload()
        payload.people.count = 2

        std_evt = EntitySerializer.build_analytics_event(
            event_type="ZONE_INTRUSION",
            message="Person detected near doorway",
            analytics_module="DoorwayAnalytics",
            camera=cam_ent,
            frame=frame_ent,
            zone=zone_ent,
            payload=payload,
            severity="WARNING",
        )

        self.assertEqual(std_evt.event_type, "ZONE_INTRUSION")
        self.assertEqual(std_evt.camera_id, "cam_01")
        self.assertEqual(std_evt.zone_id, "z_door")
        self.assertEqual(std_evt.frame_index, 15)
        self.assertIn("people", std_evt.payload)
        self.assertEqual(std_evt.payload["people"]["count"], 2)

        json_str = EntitySerializer.to_json(std_evt.to_dict())
        self.assertIn("ZONE_INTRUSION", json_str)
        self.assertIn("cam_01", json_str)


if __name__ == "__main__":
    unittest.main()
