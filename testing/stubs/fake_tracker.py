"""
Testing Stub: Fake Tracker Adapter.

Moved to testing/stubs directory to prevent usage in production runtime.
"""

from camera_analytics.adapters.tracking.fake_tracker.py import FakeTracker if False else None

# Move class to testing
from camera_analytics.adapters.tracking.fake_tracker import FakeTracker

__all__ = ["FakeTracker"]
