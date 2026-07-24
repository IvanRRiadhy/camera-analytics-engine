"""
Unit mapping tests for YOLOPoseAdapter result conversion.

Verifies that raw Ultralytics Results structures are accurately mapped to
framework-native DetectionResult, DetectionSet, Detection, BoundingBox,
PoseKeypoints, and Keypoint objects without running actual YOLO inference.
"""

from __future__ import annotations

import unittest
from dataclasses import dataclass
from typing import Any

import numpy as np

from camera_analytics.adapters.detection.yolo_pose_adapter import YOLOPoseAdapter
from camera_analytics.models.detection import DetectionClass, PoseKeypoints


@dataclass
class DummyBoxes:
    """Mock structure mimicking Ultralytics Results.boxes."""

    xyxy: np.ndarray
    conf: np.ndarray
    cls: np.ndarray

    def __len__(self) -> int:
        return len(self.xyxy)


@dataclass
class DummyKeypoints:
    """Mock structure mimicking Ultralytics Results.keypoints."""

    xy: np.ndarray
    conf: np.ndarray


class DummyResult:
    """Mock structure mimicking Ultralytics Results object."""

    def __init__(self, boxes: DummyBoxes, keypoints: DummyKeypoints | None = None) -> None:
        self.boxes = boxes
        self.keypoints = keypoints


class TestYOLOPoseMapping(unittest.TestCase):
    """Test suite for YOLOPoseAdapter conversion logic."""

    def setUp(self) -> None:
        self.adapter = YOLOPoseAdapter(confidence_threshold=0.5, iou_threshold=0.45)

    def test_convert_empty_results(self) -> None:
        """Test conversion when YOLO returns empty results."""
        detections = self.adapter._convert_results([])
        self.assertEqual(len(detections), 0)

        detections_none = self.adapter._convert_results(None)
        self.assertEqual(len(detections_none), 0)

    def test_convert_boxes_and_confidence(self) -> None:
        """Test mapping of bounding boxes, confidence, and class."""
        boxes = DummyBoxes(
            xyxy=np.array([[100.0, 200.0, 300.0, 600.0]]),
            conf=np.array([0.88]),
            cls=np.array([0]),  # Person class
        )
        dummy_results = [DummyResult(boxes=boxes)]

        detections = self.adapter._convert_results(dummy_results)

        self.assertEqual(len(detections), 1)
        det = detections[0]

        self.assertEqual(det.detection_class, DetectionClass.PERSON)
        self.assertAlmostEqual(det.confidence, 0.88, places=2)
        self.assertEqual(det.bbox.x1, 100)
        self.assertEqual(det.bbox.y1, 200)
        self.assertEqual(det.bbox.x2, 300)
        self.assertEqual(det.bbox.y2, 600)
        self.assertEqual(det.bbox.bottom_center, (200, 600))

    def test_convert_17_coco_keypoints(self) -> None:
        """Test mapping of 17 COCO keypoints into PoseKeypoints."""
        boxes = DummyBoxes(
            xyxy=np.array([[100, 200, 300, 600]]),
            conf=np.array([0.90]),
            cls=np.array([0]),
        )

        # 17 Keypoints (x, y) coordinates
        kp_xy = np.zeros((1, 17, 2), dtype=float)
        kp_conf = np.ones((1, 17), dtype=float) * 0.95

        # Set distinct coordinates for ankles
        kp_xy[0, 15] = [180.0, 580.0]  # Left ankle
        kp_xy[0, 16] = [220.0, 590.0]  # Right ankle

        dummy_results = [DummyResult(boxes=boxes, keypoints=DummyKeypoints(xy=kp_xy, conf=kp_conf))]

        detections = self.adapter._convert_results(dummy_results)

        self.assertEqual(len(detections), 1)
        det = detections[0]
        self.assertTrue(det.has_pose)
        self.assertIsNotNone(det.keypoints)
        pose: PoseKeypoints = det.keypoints  # type: ignore

        self.assertEqual(len(pose.keypoints), 17)
        self.assertEqual(pose.visible_count, 17)

        # Verify ankle keypoints
        self.assertIsNotNone(pose.left_ankle)
        self.assertIsNotNone(pose.right_ankle)
        self.assertEqual((pose.left_ankle.x, pose.left_ankle.y), (180.0, 580.0))  # type: ignore
        self.assertEqual((pose.right_ankle.x, pose.right_ankle.y), (220.0, 590.0))  # type: ignore

    def test_ground_point_calculation(self) -> None:
        """Test ground_point helper calculation from ankle keypoints and fallback."""
        boxes = DummyBoxes(
            xyxy=np.array([[100, 200, 300, 600]]),
            conf=np.array([0.90]),
            cls=np.array([0]),
        )

        # Case 1: Both ankles visible -> average of ankles
        kp_xy = np.zeros((1, 17, 2), dtype=float)
        kp_conf = np.ones((1, 17), dtype=float) * 0.9
        kp_xy[0, 15] = [180.0, 580.0]  # Left ankle
        kp_xy[0, 16] = [220.0, 590.0]  # Right ankle

        dummy_results = [DummyResult(boxes=boxes, keypoints=DummyKeypoints(xy=kp_xy, conf=kp_conf))]
        det = self.adapter._convert_results(dummy_results)[0]
        self.assertEqual(det.ground_point, (200.0, 585.0))

        # Case 2: Only left ankle visible -> left ankle coords
        kp_conf_left_only = np.zeros((1, 17), dtype=float)
        kp_conf_left_only[0, 15] = 0.95
        dummy_results2 = [DummyResult(boxes=boxes, keypoints=DummyKeypoints(xy=kp_xy, conf=kp_conf_left_only))]
        det2 = self.adapter._convert_results(dummy_results2)[0]
        self.assertEqual(det2.ground_point, (180.0, 580.0))

        # Case 3: No ankles visible -> fallback to bbox bottom_center
        kp_conf_none = np.zeros((1, 17), dtype=float)
        dummy_results3 = [DummyResult(boxes=boxes, keypoints=DummyKeypoints(xy=kp_xy, conf=kp_conf_none))]
        det3 = self.adapter._convert_results(dummy_results3)[0]
        self.assertEqual(det3.ground_point, (200.0, 600.0))

    def test_unsupported_class_filtered(self) -> None:
        """Test that non-person classes (e.g. class index 2) are filtered out."""
        boxes = DummyBoxes(
            xyxy=np.array([[10, 10, 50, 50], [100, 200, 300, 600]]),
            conf=np.array([0.9, 0.85]),
            cls=np.array([2, 0]),  # class 2 = vehicle/other, class 0 = person
        )
        dummy_results = [DummyResult(boxes=boxes)]

        detections = self.adapter._convert_results(dummy_results)
        self.assertEqual(len(detections), 1)
        self.assertEqual(detections[0].detection_class, DetectionClass.PERSON)


if __name__ == "__main__":
    unittest.main()
