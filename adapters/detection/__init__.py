"""
Detection adapters package.

Contains implementations of DetectorPort.
"""

from camera_analytics.adapters.detection.fake_detector import FakeDetector
from camera_analytics.adapters.detection.yolo_pose_adapter import YOLOPoseAdapter

__all__ = [
    "FakeDetector",
    "YOLOPoseAdapter",
]
