"""
Analytics SDK Package.

Provides reusable, plugin-based Analytics SDK foundation for developing and executing
Analytics Modules in the platform.
"""

from camera_analytics.sdk.dummy import DummyAnalytics
from camera_analytics.sdk.manager import AnalyticsManager
from camera_analytics.sdk.models import (
    AggregatedAnalyticsResult,
    AnalyticsContext,
    AnalyticsEvent,
    AnalyticsEventType,
    AnalyticsResult,
)
from camera_analytics.sdk.module import AnalyticsModule
from camera_analytics.sdk.registry import AnalyticsRegistry, register_analytics

__all__ = [
    "AnalyticsEventType",
    "AnalyticsEvent",
    "AnalyticsContext",
    "AnalyticsResult",
    "AggregatedAnalyticsResult",
    "AnalyticsModule",
    "AnalyticsRegistry",
    "register_analytics",
    "AnalyticsManager",
    "DummyAnalytics",
]
