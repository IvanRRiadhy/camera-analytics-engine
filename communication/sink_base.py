"""
Backward Compatibility Bridge for EventPublisher and Telemetry Sinks.

Redirects TelemetrySink calls directly to EventPublisher to eliminate duplicate parallel hierarchies.
"""

from camera_analytics.communication.publisher_base import EventPublisher, PublisherHealthState, PublisherMetrics
from camera_analytics.communication.registry import PublisherRegistry

# Alias TelemetrySink directly to EventPublisher for zero duplicate abstraction
TelemetrySink = EventPublisher
TelemetrySinkRegistry = PublisherRegistry

__all__ = ["TelemetrySink", "TelemetrySinkRegistry", "EventPublisher", "PublisherHealthState", "PublisherMetrics"]
