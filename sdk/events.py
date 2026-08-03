"""
Standard Enterprise Analytics Event Framework.

Provides unified, schema-versioned event models for all enterprise analytics modules:
    - EventSeverity: Classification of event severity level (INFO, WARNING, ALERT, CRITICAL).
    - EventDetailLevel: Logging detail level (SUMMARY, STANDARD, FULL).
    - StandardAnalyticsEvent: Enterprise event contract passed to Communication Layer.
"""

from __future__ import annotations

from camera_analytics.communication.models import EventDetailLevel, EventSeverity, StandardAnalyticsEvent

__all__ = [
    "EventSeverity",
    "EventDetailLevel",
    "StandardAnalyticsEvent",
]
