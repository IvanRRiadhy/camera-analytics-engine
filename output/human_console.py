"""
Human-readable Console Output Provider implementation.
"""

from __future__ import annotations

import logging
import sys
from typing import TextIO

from camera_analytics.communication.models import StandardAnalyticsEvent
from camera_analytics.output.base import OutputProvider

logger = logging.getLogger(__name__)


class HumanConsoleOutputProvider(OutputProvider):
    """OutputProvider rendering events in a formatted, human-readable terminal line."""

    def __init__(self, name: str = "human_console", stream: TextIO = sys.stdout, enabled: bool = True) -> None:
        super().__init__(name=name, enabled=enabled)
        self._stream = stream

    def output(self, event: StandardAnalyticsEvent) -> bool:
        if not self._enabled:
            return False

        line = (
            f"[{event.timestamp}] [{event.severity:7s}] Camera={event.camera_id} "
            f"Module={event.analytics_module} Event={event.event_type} | Message: {event.message}\n"
        )
        try:
            self._stream.write(line)
            self._stream.flush()
            return True
        except Exception as exc:
            logger.error("HumanConsoleOutputProvider failed: %s", exc)
            return False

    def flush(self) -> None:
        try:
            self._stream.flush()
        except Exception:
            pass
