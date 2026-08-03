"""
Detection adapters package.

Contains production implementations of DetectorPort.
"""

from camera_analytics.adapters.detection.yolo_pose_adapter import YOLOPoseAdapter

__all__ = [
    "YOLOPoseAdapter",
]
