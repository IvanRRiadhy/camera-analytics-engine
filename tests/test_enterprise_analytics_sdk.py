"""
Unit Tests for Sprint 12.0 Enterprise Analytics SDK & Standard Event Framework.

Verifies:
    1. StandardAnalyticsEvent model and EventSeverity serialization.
    2. Execution and event generation across all 8 enterprise analytics modules:
       - ZoneOccupancyModule
       - ZoneEnterModule
       - ZoneExitModule
       - DwellTimeModule
       - LoiteringModule
       - CrowdDetectionModule
       - DirectionDetectionModule
       - QueueDetectionModule
    3. Integration with AnalyticsRuntime Kernel and Plugin Discovery/Loader.
"""

import unittest
from camera_analytics.entities.models import (
    BoundingBoxEntity,
    CameraEntity,
    DirectionEntity,
    FrameEntity,
    GroundPointEntity,
    TrackEntity,
    VelocityEntity,
    ZoneEntity,
    ZoneState,
)

from camera_analytics.plugins.crowd_detection.module import CrowdDetectionModule
from camera_analytics.plugins.direction_detection.module import DirectionDetectionModule
from camera_analytics.plugins.dwell_time.module import DwellTimeModule
from camera_analytics.plugins.loitering.module import LoiteringModule
from camera_analytics.plugins.queue_detection.module import QueueDetectionModule
from camera_analytics.plugins.zone_enter.module import ZoneEnterModule
from camera_analytics.plugins.zone_exit.module import ZoneExitModule
from camera_analytics.plugins.zone_occupancy.module import ZoneOccupancyModule
from camera_analytics.runtime import AnalyticsRuntime
from camera_analytics.scene.models import Scene, SceneMetadata
from camera_analytics.sdk import EventSeverity, StandardAnalyticsEvent


class TestEnterpriseAnalyticsSDK(unittest.TestCase):
    """Test suite for Enterprise Analytics SDK & Standard Event Framework."""

    def setUp(self) -> None:
        """Set up test environment."""
        self.camera = CameraEntity(camera_id="cam_test", camera_name="Test Camera")
        self.frame = FrameEntity(frame_index=10, timestamp=10.0, frame_width=1920, frame_height=1080)
        self.zone_a = ZoneEntity(zone_id="zone_a", zone_name="Lobby", current_state=ZoneState.INSIDE)
        self.zone_b = ZoneEntity(zone_id="zone_b", zone_name="Exit Gate", current_state=ZoneState.OUTSIDE)

        self.track_1 = TrackEntity(
            track_id=1,
            track_age=15,
            bbox=BoundingBoxEntity(100, 100, 200, 300),
            ground_point=GroundPointEntity(150, 300),
            velocity=VelocityEntity(vx=0.5, vy=0.2),
            direction=DirectionEntity(heading_degrees=90.0, cardinal_direction="E"),
        )
        self.track_2 = TrackEntity(
            track_id=2,
            track_age=25,
            bbox=BoundingBoxEntity(300, 300, 400, 500),
            ground_point=GroundPointEntity(350, 500),
            velocity=VelocityEntity(vx=0.0, vy=-15.0),
            direction=DirectionEntity(heading_degrees=180.0, cardinal_direction="S"),
        )

        self.scene = Scene(
            camera=self.camera,
            frame=self.frame,
            tracks=(self.track_1, self.track_2),
            zones=(self.zone_a, self.zone_b),
            metadata=SceneMetadata(camera_id="cam_test", frame_index=10, timestamp=10.0),
        )

    def test_standard_analytics_event_creation(self) -> None:
        """Test StandardAnalyticsEvent creation and dictionary serialization."""
        evt = StandardAnalyticsEvent(
            event_type="TEST_EVENT",
            source_module="test_mod",
            timestamp=10.0,
            camera_id="cam_test",
            severity=EventSeverity.WARNING,
            track_id=1,
            zone_id="zone_a",
            payload={"count": 5},
        )
        d = evt.to_dict()
        self.assertEqual(d["event_type"], "TEST_EVENT")
        self.assertEqual(d["source_module"], "test_mod")
        self.assertEqual(d["severity"], "WARNING")
        self.assertEqual(d["track_id"], 1)
        self.assertEqual(d["zone_id"], "zone_a")
        self.assertEqual(d["payload"]["count"], 5)

    def test_zone_occupancy_module(self) -> None:
        """Test ZoneOccupancyModule execution and event generation."""
        mod = ZoneOccupancyModule()
        res = mod.process_scene(self.scene)
        self.assertIn("zone_occupancy", res.module_name)
        self.assertGreaterEqual(len(res.events), 1)

    def test_zone_enter_module(self) -> None:
        """Test ZoneEnterModule entry transition detection."""
        mod = ZoneEnterModule()
        res = mod.process_scene(self.scene)
        self.assertGreaterEqual(len(res.events), 1)
        evt_data = res.events[0].data
        self.assertEqual(evt_data["event_type"], "ZONE_ENTER")

    def test_zone_exit_module(self) -> None:
        """Test ZoneExitModule exit transition detection."""
        mod = ZoneExitModule()
        # Scene 1: Inside
        mod.process_scene(self.scene)
        # Scene 2: Outside
        scene_empty = Scene(
            camera=self.camera,
            frame=FrameEntity(frame_index=11, timestamp=11.0, frame_width=1920, frame_height=1080),
            tracks=(),
            zones=(self.zone_a, self.zone_b),
            metadata=SceneMetadata(camera_id="cam_test", frame_index=11, timestamp=11.0),
        )
        res_exit = mod.process_scene(scene_empty)
        self.assertGreaterEqual(len(res_exit.events), 1)
        evt_data = res_exit.events[0].data
        self.assertEqual(evt_data["event_type"], "ZONE_EXIT")

    def test_dwell_time_module(self) -> None:
        """Test DwellTimeModule cumulative dwell duration calculation."""
        mod = DwellTimeModule()
        mod.dwell_threshold_seconds = 2.0
        # Frame at t=10.0
        mod.process_scene(self.scene)
        # Frame at t=13.0 (> 2.0s)
        scene_later = Scene(
            camera=self.camera,
            frame=FrameEntity(frame_index=15, timestamp=13.0, frame_width=1920, frame_height=1080),
            tracks=(self.track_1,),
            zones=(self.zone_a,),
            metadata=SceneMetadata(camera_id="cam_test", frame_index=15, timestamp=13.0),
        )
        res = mod.process_scene(scene_later)
        self.assertGreaterEqual(len(res.events), 1)
        evt_data = res.events[0].data
        self.assertEqual(evt_data["event_type"], "DWELL_TIME")

    def test_loitering_module(self) -> None:
        """Test LoiteringModule stationary loitering detection."""
        mod = LoiteringModule()
        mod.loitering_threshold_seconds = 2.0
        mod.process_scene(self.scene)

        scene_later = Scene(
            camera=self.camera,
            frame=FrameEntity(frame_index=15, timestamp=13.0, frame_width=1920, frame_height=1080),
            tracks=(self.track_1,),
            zones=(self.zone_a,),
            metadata=SceneMetadata(camera_id="cam_test", frame_index=15, timestamp=13.0),
        )
        res = mod.process_scene(scene_later)
        self.assertGreaterEqual(len(res.events), 1)
        evt_data = res.events[0].data
        self.assertEqual(evt_data["event_type"], "LOITERING")

    def test_crowd_detection_module(self) -> None:
        """Test CrowdDetectionModule track density threshold alert."""
        mod = CrowdDetectionModule()
        mod.crowd_threshold = 2
        res = mod.process_scene(self.scene)
        self.assertGreaterEqual(len(res.events), 1)
        evt_data = res.events[0].data
        self.assertEqual(evt_data["event_type"], "CROWD_ALERT")

    def test_direction_detection_module(self) -> None:
        """Test DirectionDetectionModule cardinal wrong-direction violation."""
        mod = DirectionDetectionModule()
        mod.min_speed_threshold = 5.0
        res = mod.process_scene(self.scene)
        self.assertGreaterEqual(len(res.events), 1)
        evt_data = res.events[0].data
        self.assertEqual(evt_data["event_type"], "DIRECTION_VIOLATION")

    def test_queue_detection_module(self) -> None:
        """Test QueueDetectionModule queue length alert."""
        mod = QueueDetectionModule()
        mod.max_queue_length = 2
        res = mod.process_scene(self.scene)
        self.assertGreaterEqual(len(res.events), 1)
        evt_data = res.events[0].data
        self.assertEqual(evt_data["event_type"], "QUEUE_ALERT")

    def test_runtime_kernel_plugin_loading(self) -> None:
        """Test loading all 8 analytics modules into AnalyticsRuntime Kernel dynamically."""
        runtime = AnalyticsRuntime()
        report = runtime.load_plugins_from_directory("camera_analytics/plugins")

        self.assertGreaterEqual(report.loaded_count, 8)
        runtime.initialize()
        runtime.start()

        aggregated = runtime.process_scene(self.scene)
        self.assertGreaterEqual(len(aggregated.results), 8)

        runtime.stop()
        runtime.dispose()


if __name__ == "__main__":
    unittest.main()
