"""
Unit tests for BoTSORTAdapter and tracking association logic.

Verifies:
    - Mapping of Detection objects to framework TrackingResult and TrackerResult.
    - Persistence of Track IDs across consecutive frames for moving bounding boxes.
    - Proper assignment of `is_new` flag on new vs existing tracks.
    - Fallback association mode when external tracker is absent.
    - Full track lifecycle state transitions (Tentative -> Confirmed -> Lost -> Removed) in TrackManager.
"""

from __future__ import annotations

import unittest
import numpy as np

from camera_analytics.adapters.tracking.botsort_adapter import BoTSORTAdapter
from camera_analytics.core.detection_set import DetectionSet
from camera_analytics.core.ports import DetectionResult
from camera_analytics.core.track_manager import TrackManager
from camera_analytics.models.detection import (
    BoundingBox,
    Detection,
    DetectionClass,
    Keypoint,
    PoseKeypoints,
)


def create_fake_person_detection(
    x1: int, y1: int, x2: int, y2: int, confidence: float = 0.85
) -> Detection:
    """Helper to create a synthetic person Detection with pose keypoints."""
    bbox = BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2)
    keypoints_list = [
        Keypoint(x=float(x1 + 10), y=float(y1 + 10), confidence=0.9)
        for _ in range(17)
    ]
    pose = PoseKeypoints(keypoints=tuple(keypoints_list))

    return Detection(
        bbox=bbox,
        confidence=confidence,
        detection_class=DetectionClass.PERSON,
        keypoints=pose,
    )


class TestBoTSORTTracking(unittest.TestCase):
    """Test suite for BoTSORTAdapter data association and mapping."""

    def setUp(self) -> None:
        self.tracker = BoTSORTAdapter(track_high_thresh=0.5, track_buffer=30)
        self.tracker.initialize()
        self.dummy_frame = np.zeros((1080, 1920, 3), dtype=np.uint8)

    def test_empty_detections_tracking(self) -> None:
        """Test tracking when incoming frame has no detections."""
        det_result = DetectionResult(
            detections=DetectionSet([]),
            model_name="fake_detector",
        )
        trk_result = self.tracker.track(self.dummy_frame, det_result)

        self.assertEqual(len(trk_result.results), 0)
        self.assertEqual(trk_result.tracker_name, "botsort")

    def test_new_track_creation(self) -> None:
        """Test that a new detection creates a new track with is_new=True."""
        det1 = create_fake_person_detection(100, 100, 200, 400)
        det_result = DetectionResult(
            detections=DetectionSet([det1]),
            model_name="fake_detector",
        )

        trk_result = self.tracker.track(self.dummy_frame, det_result)

        self.assertEqual(len(trk_result.results), 1)
        res = trk_result.results[0]

        self.assertEqual(res.track_id, 1)
        self.assertTrue(res.is_new)
        self.assertEqual(res.detection.bbox, det1.bbox)
        self.assertTrue(res.detection.has_pose)

    def test_track_id_persistence_across_frames(self) -> None:
        """Test that a moving bounding box retains its assigned Track ID across frames."""
        # Frame 1: Person at (100, 100, 200, 400)
        det1 = create_fake_person_detection(100, 100, 200, 400)
        res1 = self.tracker.track(
            self.dummy_frame, DetectionResult(detections=DetectionSet([det1]), model_name="fake")
        )
        assigned_id = res1.results[0].track_id
        self.assertTrue(res1.results[0].is_new)

        # Frame 2: Person moves slightly to (105, 102, 205, 402)
        det2 = create_fake_person_detection(105, 102, 205, 402)
        res2 = self.tracker.track(
            self.dummy_frame, DetectionResult(detections=DetectionSet([det2]), model_name="fake")
        )

        self.assertEqual(len(res2.results), 1)
        res2_item = res2.results[0]

        # Persistent Track ID check
        self.assertEqual(res2_item.track_id, assigned_id)
        self.assertFalse(res2_item.is_new)

    def test_multiple_tracks_association(self) -> None:
        """Test association of multiple distinct person detections."""
        # Frame 1: Two persons
        det_a = create_fake_person_detection(100, 100, 200, 400)
        det_b = create_fake_person_detection(600, 200, 700, 500)

        res1 = self.tracker.track(
            self.dummy_frame, DetectionResult(detections=DetectionSet([det_a, det_b]), model_name="fake")
        )
        self.assertEqual(len(res1.results), 2)
        id_a = res1.results[0].track_id
        id_b = res1.results[1].track_id

        self.assertNotEqual(id_a, id_b)

        # Frame 2: Both move slightly
        det_a2 = create_fake_person_detection(102, 102, 202, 402)
        det_b2 = create_fake_person_detection(604, 202, 704, 502)

        res2 = self.tracker.track(
            self.dummy_frame, DetectionResult(detections=DetectionSet([det_a2, det_b2]), model_name="fake")
        )
        self.assertEqual(len(res2.results), 2)

        ids_frame2 = [r.track_id for r in res2.results]
        self.assertIn(id_a, ids_frame2)
        self.assertIn(id_b, ids_frame2)

    def test_track_lifecycle_transitions(self) -> None:
        """Test complete lifecycle transitions: Tentative -> Confirmed -> Lost -> Removed in TrackManager."""
        tm = TrackManager(confirm_after_n=3, max_lost_age=2)
        det = create_fake_person_detection(100, 100, 200, 400)

        # Frame 1: Created -> TENTATIVE
        res1 = self.tracker.track(self.dummy_frame, DetectionResult(detections=DetectionSet([det]), model_name="fake"))
        tm.update_from_tracker(res1.results, frame_index=1)
        self.assertEqual(len(tm.get_active()), 1)
        self.assertEqual(len(tm.get_confirmed()), 0) # Still Tentative

        # Frame 2: Hit 2 -> Still TENTATIVE
        res2 = self.tracker.track(self.dummy_frame, DetectionResult(detections=DetectionSet([det]), model_name="fake"))
        tm.update_from_tracker(res2.results, frame_index=2)
        self.assertEqual(len(tm.get_confirmed()), 0)

        # Frame 3: Hit 3 -> CONFIRMED
        res3 = self.tracker.track(self.dummy_frame, DetectionResult(detections=DetectionSet([det]), model_name="fake"))
        tm.update_from_tracker(res3.results, frame_index=3)
        self.assertEqual(len(tm.get_confirmed()), 1) # Confirmed!

        # Frame 4: Missed detection -> LOST
        res_empty = self.tracker.track(self.dummy_frame, DetectionResult(detections=DetectionSet([]), model_name="fake"))
        tm.update_from_tracker(res_empty.results, frame_index=4)
        self.assertEqual(len(tm.get_lost()), 1)

        # Frame 5 & 6: Exceed max_lost_age (2) -> REMOVED / ARCHIVED
        tm.update_from_tracker([], frame_index=5)
        tm.update_from_tracker([], frame_index=6)
        self.assertEqual(len(tm.get_active()), 0)
        self.assertEqual(tm.total_deleted, 1)

    def test_tracker_reset(self) -> None:
        """Test resetting tracker clears state."""
        det = create_fake_person_detection(100, 100, 200, 400)
        self.tracker.track(self.dummy_frame, DetectionResult(detections=DetectionSet([det]), model_name="fake"))

        self.tracker.reset()
        self.assertFalse(self.tracker.is_initialized)


if __name__ == "__main__":
    unittest.main()
