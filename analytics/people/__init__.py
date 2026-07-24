"""
People analytics sub-package.

Exports PeopleAnalytics module for registration with the Pipeline.

Usage::

    from camera_analytics.analytics.people import PeopleAnalytics

    pipeline.register(PeopleAnalytics())
"""

from camera_analytics.analytics.people.people_module import PeopleAnalytics

__all__ = ["PeopleAnalytics"]
