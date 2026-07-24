"""
Camera Analytics Framework.

A modular, extensible framework for real-time video analytics.
Built on YOLO, BoT-SORT, and OpenCV with a plugin-based architecture
for domain-specific analytics modules.

Quick start::

    from camera_analytics.core import Pipeline, Config
    from camera_analytics.analytics.people import PeopleAnalytics

    pipeline = Pipeline(Config.from_dict({...}))
    pipeline.register(PeopleAnalytics())
    pipeline.start()
"""

__version__ = "0.1.0"
