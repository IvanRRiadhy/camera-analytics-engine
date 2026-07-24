"""
Unit tests for Scene Layer.

Verifies:
    - Immutability of Scene dataclass (raising FrozenInstanceError on attribute modification).
    - SceneMetadata and SceneStatistics accuracy.
    - SceneBuilder fluent construction.
    - SceneFactory manufacturing Scene directly from runtime objects.
    - Track lookup and Zone lookup methods.
"""

import dataclasses
import unittest

from camera_analytics.entities.models import (
    BoundingBoxEntity,
    CameraEntity,
    FrameEntity,
    TrackEntity,
    ZoneEntity,
    ZoneState,
)
from camera_analytics.scene.builder import SceneBuilder
from camera_analytics.scene.factory import SceneFactory
from camera_analytics.scene.models import (
    Scene,
    SceneMetadata,
    SceneStatistics,
)


class TestSceneLayer(unittest.TestCase):
    """Test suite for Scene Layer components."""

    def setUp(self) -> None:
        """Set up standard entity fixtures."""
        self.camera_ent = CameraEntity(camera_id="cam_lobby", camera_name="Lobby Camera")
        self.frame_ent = FrameEntity(frame_index=10, timestamp=1.0, frame_width=1920, frame_height=1080)
        self.track_1 = TrackEntity(track_id=1, confidence=0.9, bbox=BoundingBoxEntity(10, 10, 100, 100))
        self.track_2 = TrackEntity(track_id=2, confidence=0.8, bbox=BoundingBoxEntity(50, 50, 150, 150))
        self.zone_1 = ZoneEntity(zone_id="z_entrance", zone_name="Entrance Area", current_state=ZoneState.INSIDE)

    def test_scene_immutability(self) -> None:
        """Test that Scene is strictly read-only and immutable."""
        scene = (
            SceneBuilder()
            .set_camera(self.camera_ent)
            .set_frame(self.frame_ent)
            .set_tracks([self.track_1, self.track_2])
            .set_zones([self.zone_1])
            .build()
        )

        # Attribute assignment must raise FrozenInstanceError
        with self.assertRaises(dataclasses.FrozenInstanceError):
            scene.camera = CameraEntity(camera_id="hacked_cam", camera_name="Hacked")  # type: ignore

        with self.assertRaises(dataclasses.FrozenInstanceError):
            scene.tracks = ()  # type: ignore

    def test_scene_track_and_zone_counts(self) -> None:
        """Test that Scene accurately reflects track and zone counts and lookup helpers."""
        scene = (
            SceneBuilder()
            .set_camera(self.camera_ent)
            .set_frame(self.frame_ent)
            .set_tracks([self.track_1, self.track_2])
            .set_zones([self.zone_1])
            .build()
        )

        self.assertEqual(len(scene.tracks), 2)
        self.assertEqual(len(scene.zones), 1)
        self.assertEqual(scene.statistics.active_track_count, 2)
        self.assertEqual(scene.statistics.zone_count, 1)

        # Lookup helpers
        found_track = scene.get_track_by_id(2)
        self.assertIsNotNone(found_track)
        self.assertEqual(found_track.track_id, 2)

        found_zone = scene.get_zone_by_id("z_entrance")
        self.assertIsNotNone(found_zone)
        self.assertEqual(found_zone.zone_name, "Entrance Area")

    def test_scene_metadata_and_statistics(self) -> None:
        """Test SceneMetadata and SceneStatistics data dictionary generation."""
        meta = SceneMetadata(frame_index=42, timestamp=4.2, camera_id="cam_lobby")
        stats = SceneStatistics(active_track_count=5, zone_count=2, fps=25.0)

        scene = Scene(
            camera=self.camera_ent,
            frame=self.frame_ent,
            tracks=(self.track_1,),
            zones=(self.zone_1,),
            statistics=stats,
            metadata=meta,
        )

        d = scene.to_dict()
        self.assertEqual(d["metadata"]["frame_index"], 42)
        self.assertEqual(d["statistics"]["active_track_count"], 5)
        self.assertEqual(d["camera"]["camera_id"], "cam_lobby")

    def test_scene_factory(self) -> None:
        """Test SceneFactory manufacturing Scene directly from parameters."""
        scene = SceneFactory.create_scene(
            frame_index=100,
            timestamp=10.0,
        )

        self.assertIsInstance(scene, Scene)
        self.assertEqual(scene.frame.frame_index, 100)
        self.assertEqual(scene.metadata.frame_index, 100)


if __name__ == "__main__":
    unittest.main()
