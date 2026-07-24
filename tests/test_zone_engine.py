"""
Unit tests for ZoneEngine spatial relationship processing.

Verifies:
    - Point In Polygon containment algorithm.
    - Single firing of ENTER event upon crossing into zone.
    - Single firing of EXIT event upon leaving zone.
    - STAY event generation and dwell_frames increment while inside zone.
    - Multi-Zone spatial state tracking.
"""

from __future__ import annotations

import unittest

from camera_analytics.core.zone_engine import (
    TrackZoneState,
    ZoneEngine,
    ZoneEventType,
)
from camera_analytics.models.detection import (
    BoundingBox,
    Detection,
    DetectionClass,
    Keypoint,
    PoseKeypoints,
)
from camera_analytics.models.track import Track
from camera_analytics.models.zone import Point, Zone, ZoneType


def create_track_at_ground_point(track_id: int, gx: int, gy: int) -> Track:
    """Helper to construct a Track object with a specific ground_point (gx, gy)."""
    # Place bbox bottom center at (gx, gy)
    x1, y1 = gx - 20, gy - 100
    x2, y2 = gx + 20, gy
    bbox = BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2)

    # Keypoints set to None so ground_point falls back to bbox bottom center (gx, gy)
    det = Detection(
        bbox=bbox,
        confidence=0.9,
        detection_class=DetectionClass.PERSON,
        keypoints=None,
    )
    track = Track(track_id=track_id, detection=det)
    track.hit_count = 5  # Confirmed track
    return track


def create_polygon_zone(zone_id: str, name: str, x1: int, y1: int, x2: int, y2: int) -> Zone:
    """Helper to construct a rectangular REGION Zone."""
    points = [
        Point(x1, y1),
        Point(x2, y1),
        Point(x2, y2),
        Point(x1, y2),
    ]
    return Zone(
        zone_id=zone_id,
        name=name,
        zone_type=ZoneType.REGION,
        points=points,
        color=(0, 255, 0),
    )


class TestZoneEngine(unittest.TestCase):
    """Test suite for ZoneEngine state machine and event generation."""

    def setUp(self) -> None:
        self.engine = ZoneEngine()
        self.zone_a = create_polygon_zone("zone_a", "Entrance", 100, 100, 500, 500)
        self.zone_b = create_polygon_zone("zone_b", "Restricted", 600, 100, 900, 500)

    def test_point_in_polygon(self) -> None:
        """Test Point In Polygon containment logic on Zone."""
        self.assertTrue(self.zone_a.contains_point(250, 250))
        self.assertFalse(self.zone_a.contains_point(50, 50))
        self.assertFalse(self.zone_a.contains_point(550, 250))

    def test_enter_event_single_fire(self) -> None:
        """Test that entering a zone fires exactly ONE ENTER event."""
        # Frame 1: Track is OUTSIDE (x=50, y=50)
        track1 = create_track_at_ground_point(track_id=1, gx=50, gy=50)
        res1 = self.engine.process([track1], [self.zone_a], frame_index=1, timestamp=0.0)

        self.assertEqual(len(res1.events), 0)
        self.assertEqual(res1.track_states[1]["zone_a"], TrackZoneState.OUTSIDE)

        # Frame 2: Track moves INSIDE (x=200, y=200) -> Should trigger ENTER
        track2 = create_track_at_ground_point(track_id=1, gx=200, gy=200)
        res2 = self.engine.process([track2], [self.zone_a], frame_index=2, timestamp=0.1)

        self.assertEqual(len(res2.events), 1)
        event = res2.events[0]
        self.assertEqual(event.event_type, ZoneEventType.ENTER)
        self.assertEqual(event.track_id, 1)
        self.assertEqual(event.zone_id, "zone_a")
        self.assertEqual(res2.track_states[1]["zone_a"], TrackZoneState.ENTER)

        # Frame 3: Track remains INSIDE (x=210, y=210) -> Should NOT trigger ENTER again
        track3 = create_track_at_ground_point(track_id=1, gx=210, gy=210)
        res3 = self.engine.process([track3], [self.zone_a], frame_index=3, timestamp=0.2)

        self.assertEqual(len(res3.events), 1)
        self.assertEqual(res3.events[0].event_type, ZoneEventType.STAY)
        self.assertEqual(res3.track_states[1]["zone_a"], TrackZoneState.INSIDE)

    def test_exit_event_single_fire(self) -> None:
        """Test that exiting a zone fires exactly ONE EXIT event."""
        # Frame 1: Track inside (x=200, y=200) -> ENTER
        track = create_track_at_ground_point(1, 200, 200)
        self.engine.process([track], [self.zone_a], frame_index=1)

        # Frame 2: Track inside (x=200, y=200) -> INSIDE
        self.engine.process([track], [self.zone_a], frame_index=2)

        # Frame 3: Track moves OUTSIDE (x=50, y=50) -> EXIT
        track_out = create_track_at_ground_point(1, 50, 50)
        res_exit = self.engine.process([track_out], [self.zone_a], frame_index=3)

        self.assertEqual(len(res_exit.events), 1)
        event = res_exit.events[0]
        self.assertEqual(event.event_type, ZoneEventType.EXIT)
        self.assertEqual(event.track_id, 1)
        self.assertEqual(res_exit.track_states[1]["zone_a"], TrackZoneState.EXIT)

        # Frame 4: Track remains OUTSIDE (x=40, y=40) -> OUTSIDE (No EXIT event)
        track_out2 = create_track_at_ground_point(1, 40, 40)
        res_out = self.engine.process([track_out2], [self.zone_a], frame_index=4)

        self.assertEqual(len(res_out.events), 0)
        self.assertEqual(res_out.track_states[1]["zone_a"], TrackZoneState.OUTSIDE)

    def test_stay_event_dwell_counting(self) -> None:
        """Test STAY event generation and dwell frame counter accumulation."""
        track = create_track_at_ground_point(1, 300, 300)

        # Frame 1 (ENTER) -> dwell = 1
        res1 = self.engine.process([track], [self.zone_a], frame_index=1)
        self.assertEqual(res1.events[0].dwell_frames, 1)

        # Frame 2 (STAY) -> dwell = 2
        res2 = self.engine.process([track], [self.zone_a], frame_index=2)
        self.assertEqual(res2.events[0].dwell_frames, 2)

        # Frame 3 (STAY) -> dwell = 3
        res3 = self.engine.process([track], [self.zone_a], frame_index=3)
        self.assertEqual(res3.events[0].dwell_frames, 3)

    def test_multi_zone_tracking(self) -> None:
        """Test independent spatial tracking across multiple zones."""
        # Track 1 inside Zone A, Track 2 inside Zone B
        t1 = create_track_at_ground_point(1, 200, 200) # Zone A
        t2 = create_track_at_ground_point(2, 700, 300) # Zone B

        res = self.engine.process([t1, t2], [self.zone_a, self.zone_b], frame_index=1)

        # 2 ENTER events should fire
        self.assertEqual(len(res.events), 2)

        states_t1 = res.track_states[1]
        states_t2 = res.track_states[2]

        self.assertEqual(states_t1["zone_a"], TrackZoneState.ENTER)
        self.assertEqual(states_t1["zone_b"], TrackZoneState.OUTSIDE)

        self.assertEqual(states_t2["zone_a"], TrackZoneState.OUTSIDE)
        self.assertEqual(states_t2["zone_b"], TrackZoneState.ENTER)


if __name__ == "__main__":
    unittest.main()
