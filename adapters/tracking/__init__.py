"""
Tracking adapters package.

Contains implementations of TrackerPort.
"""

from camera_analytics.adapters.tracking.botsort_adapter import BoTSORTAdapter
from camera_analytics.adapters.tracking.fake_tracker import FakeTracker

__all__ = [
    "FakeTracker",
    "BoTSORTAdapter",
]
