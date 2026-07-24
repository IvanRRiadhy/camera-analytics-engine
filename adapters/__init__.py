"""
Adapters package.

Contains concrete implementations and stubs of framework ports:
    - detection/  : DetectorPort implementations (FakeDetector, YOLOPoseAdapter)
    - tracking/   : TrackerPort implementations (FakeTracker, BoTSORTAdapter)
"""

from camera_analytics.adapters.detection import FakeDetector, YOLOPoseAdapter
from camera_analytics.adapters.tracking import BoTSORTAdapter, FakeTracker

__all__ = [
    "FakeDetector",
    "YOLOPoseAdapter",
    "FakeTracker",
    "BoTSORTAdapter",
]
