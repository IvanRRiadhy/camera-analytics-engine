"""
Analytics modules package.

Contains all domain-specific analytics modules that can be
registered with the Pipeline. Each sub-package implements one
analytics domain (people, vehicles, PPE, etc.).

Usage::

    from camera_analytics.analytics.people import PeopleAnalytics
"""

from camera_analytics.analytics.people import PeopleAnalytics

__all__ = ["PeopleAnalytics"]
