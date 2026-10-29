"""
Unit tests for ZoneManager zone ID resolution, precedence, fallback, and duplicate handling.
"""

from __future__ import annotations

import logging
import unittest
from typing import Any, List

from camera_analytics.core.spatial.zone_manager import ZoneManager


class TestZoneManagerIdResolution(unittest.TestCase):
    """Test suite verifying zone ID extraction precedence, fallback, and deduplication."""

    def setUp(self) -> None:
        self.zone_manager = ZoneManager()
        self.camera_id = "cam_test_01"
        self.dummy_poly = [[0, 0], [100, 0], [100, 100], [0, 100]]

    def test_zone_id_keyed_by_zone_id(self) -> None:
        """Zones with 'zone_id' are keyed by it rather than positional z_N."""
        raw = [
            {"zone_id": "critical_zone_01", "name": "Restricted Area", "points": self.dummy_poly},
            {"zone_id": "lobby_main_01", "name": "Lobby Area", "points": self.dummy_poly},
        ]
        zones = self.zone_manager.load_zones_from_backend(self.camera_id, raw)
        self.assertEqual(len(zones), 2)
        self.assertEqual(zones[0].id, "critical_zone_01")
        self.assertEqual(zones[1].id, "lobby_main_01")
        self.assertIsNotNone(self.zone_manager.get_zone_by_id(self.camera_id, "critical_zone_01"))
        self.assertIsNotNone(self.zone_manager.get_zone_by_id(self.camera_id, "lobby_main_01"))

    def test_id_and_zoneId_backward_compatibility(self) -> None:
        """Configurations using 'id' or 'zoneId' still work as expected."""
        raw = [
            {"id": "zone_alpha", "name": "Alpha", "points": self.dummy_poly},
            {"zoneId": "zone_beta", "name": "Beta", "points": self.dummy_poly},
        ]
        zones = self.zone_manager.load_zones_from_backend(self.camera_id, raw)
        self.assertEqual(len(zones), 2)
        self.assertEqual(zones[0].id, "zone_alpha")
        self.assertEqual(zones[1].id, "zone_beta")
        self.assertIsNotNone(self.zone_manager.get_zone_by_id(self.camera_id, "zone_alpha"))
        self.assertIsNotNone(self.zone_manager.get_zone_by_id(self.camera_id, "zone_beta"))

    def test_no_id_falls_back_to_positional_z_n(self) -> None:
        """Configurations with no ID keys fall back to positional z_N."""
        raw = [
            {"name": "Unnamed 1", "points": self.dummy_poly},
            {"name": "Unnamed 2", "points": self.dummy_poly},
        ]
        zones = self.zone_manager.load_zones_from_backend(self.camera_id, raw)
        self.assertEqual(len(zones), 2)
        self.assertEqual(zones[0].id, "z_0")
        self.assertEqual(zones[1].id, "z_1")

    def test_zone_id_wins_precedence(self) -> None:
        """'zone_id' takes precedence when several keys exist simultaneously."""
        raw = [
            {
                "zone_id": "priority_winner",
                "id": "second_place",
                "zoneId": "third_place",
                "name": "Conflict Zone",
                "points": self.dummy_poly,
            }
        ]
        zones = self.zone_manager.load_zones_from_backend(self.camera_id, raw)
        self.assertEqual(len(zones), 1)
        self.assertEqual(zones[0].id, "priority_winner")
        self.assertIsNotNone(self.zone_manager.get_zone_by_id(self.camera_id, "priority_winner"))
        self.assertIsNone(self.zone_manager.get_zone_by_id(self.camera_id, "second_place"))
        self.assertIsNone(self.zone_manager.get_zone_by_id(self.camera_id, "third_place"))

    def test_duplicate_ids_warning_and_skipped(self) -> None:
        """Duplicate zone IDs within one camera emit a WARNING and the later duplicate is skipped."""
        raw = [
            {"zone_id": "dup_zone", "name": "First Definition", "points": self.dummy_poly},
            {"zone_id": "dup_zone", "name": "Duplicate Definition", "points": self.dummy_poly},
            {"zone_id": "unique_zone", "name": "Unique Zone", "points": self.dummy_poly},
        ]
        with self.assertLogs("camera_analytics.core.spatial.zone_manager", level="WARNING") as log_ctx:
            zones = self.zone_manager.load_zones_from_backend(self.camera_id, raw)

        # Confirm duplicate warning was emitted
        self.assertTrue(any("Duplicate zone_id 'dup_zone'" in msg for msg in log_ctx.output))

        # Confirm later duplicate was skipped, keeping only the first authoritative definition
        self.assertEqual(len(zones), 2)
        self.assertEqual(zones[0].id, "dup_zone")
        self.assertEqual(zones[0].name, "First Definition")
        self.assertEqual(zones[1].id, "unique_zone")
        self.assertEqual(self.zone_manager.get_zone_by_id(self.camera_id, "dup_zone").name, "First Definition")

    def test_same_zone_id_allowed_across_different_cameras(self) -> None:
        """The same zone_id is permitted across different cameras without conflict or warning."""
        raw_cam1 = [{"zone_id": "perimeter_zone", "name": "Cam 1 Perimeter", "points": self.dummy_poly}]
        raw_cam2 = [{"zone_id": "perimeter_zone", "name": "Cam 2 Perimeter", "points": self.dummy_poly}]

        zones_cam1 = self.zone_manager.load_zones_from_backend("cam_01", raw_cam1)
        zones_cam2 = self.zone_manager.load_zones_from_backend("cam_02", raw_cam2)

        self.assertEqual(len(zones_cam1), 1)
        self.assertEqual(len(zones_cam2), 1)
        self.assertEqual(zones_cam1[0].id, "perimeter_zone")
        self.assertEqual(zones_cam2[0].id, "perimeter_zone")
        self.assertEqual(self.zone_manager.get_zone_by_id("cam_01", "perimeter_zone").name, "Cam 1 Perimeter")
        self.assertEqual(self.zone_manager.get_zone_by_id("cam_02", "perimeter_zone").name, "Cam 2 Perimeter")


if __name__ == "__main__":
    unittest.main()
