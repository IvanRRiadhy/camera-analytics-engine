"""
Console Event Publisher Implementation.

Formats and prints `StandardAnalyticsEvent` objects directly to STDOUT / console
with optional severity indicators.
"""

from __future__ import annotations

import logging
import sys
import time
from typing import Any, Optional

from camera_analytics.communication.models import StandardAnalyticsEvent
from camera_analytics.communication.publisher_base import EventPublisher
from camera_analytics.communication.registry import register_publisher

logger = logging.getLogger(__name__)


@register_publisher("console")
class ConsolePublisher(EventPublisher):
    """Event Publisher that formats and outputs events to STDOUT console."""

    def __init__(
        self,
        name: str = "console_publisher",
        enabled: bool = True,
        show_payload: bool = True,
    ) -> None:
        super().__init__(name=name, enabled=enabled)
        self._show_payload = show_payload

    def on_initialize(self, config: dict[str, Any]) -> None:
        """Initialize ConsolePublisher with configuration options."""
        self._show_payload = config.get("show_payload", self._show_payload)

    def publish(self, event: StandardAnalyticsEvent, serialized_payload: str) -> bool:
        """Format and print event to console STDOUT."""
        if not self._is_running or not self._enabled:
            return False

        t_start = time.time()
        try:
            timestamp_short = event.timestamp.split("T")[-1] if "T" in event.timestamp else event.timestamp
            msg = f"[{timestamp_short}] [{event.severity}] [{event.analytics_module}] ({event.camera_id}): {event.message}"
            if self._show_payload:
                msg += f" | {serialized_payload}"

            print(msg, file=sys.stdout, flush=True)
            latency_ms = (time.time() - t_start) * 1000.0
            self.record_publish_metrics(success=True, latency_ms=latency_ms)
            return True
        except Exception as exc:
            logger.error("ConsolePublisher '%s' failed to print event: %s", self._name, exc)
            self.record_publish_metrics(success=False, latency_ms=0.0)
            return False
