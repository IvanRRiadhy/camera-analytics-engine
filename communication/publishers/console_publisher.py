"""
Console Event & Telemetry Publisher Implementation.

Formats and outputs concise 1-line operator status summaries directly to STDOUT:
`[13:22:11] Lobby | FPS 25 | People 3 | Queue 0 | Loitering 0`
"""

from __future__ import annotations

import logging
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from camera_analytics.communication.models import StandardAnalyticsEvent
from camera_analytics.communication.publisher_base import EventPublisher, PublisherHealthState
from camera_analytics.communication.registry import register_publisher

logger = logging.getLogger(__name__)


@register_publisher("console")
@register_publisher("stdout")
class ConsolePublisher(EventPublisher):
    """Event & Telemetry Publisher formatting concise operator status to STDOUT."""

    def __init__(
        self,
        name: str = "console",
        enabled: bool = True,
        show_payload: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(name=name, enabled=enabled, **kwargs)
        self._show_payload = show_payload

    def on_initialize(self, config: Dict[str, Any]) -> None:
        """Initialize ConsolePublisher configuration."""
        self._show_payload = config.get("show_payload", self._show_payload)

    def on_publish_raw(self, exchange: str, routing_key: str, payload_dict: Dict[str, Any]) -> bool:
        """Format and print concise 1-line summary to STDOUT."""
        if not self._is_running or not self._enabled:
            return False

        t_start = time.time()
        try:
            cam_id = payload_dict.get("cameraId", "Camera")
            health = payload_dict.get("health", {})
            fps = round(health.get("fps", 0.0))

            plugins = payload_dict.get("plugins", {})
            pc = plugins.get("peopleCounting", {})
            qd = plugins.get("queueDetection", {})
            lo = plugins.get("loitering", {})

            pc_curr = pc.get("current", pc.get("summary", {}).get("current", 0))
            qd_len = qd.get("queueLength", qd.get("summary", {}).get("queueLength", 0))
            lo_act = lo.get("active", lo.get("summary", {}).get("active", 0))

            ts_raw = payload_dict.get("timestamp", datetime.now(timezone.utc).isoformat())
            if "T" in ts_raw:
                time_str = ts_raw.split("T")[-1].split(".")[0]
            else:
                time_str = datetime.now().strftime("%H:%M:%S")

            line = f"[{time_str}] {cam_id} | FPS {fps} | People {pc_curr} | Queue {qd_len} | Loitering {lo_act}"
            print(line, file=sys.stdout, flush=True)

            latency_ms = (time.time() - t_start) * 1000.0
            self.metrics.record_success(latency_ms)
            self.set_state(PublisherHealthState.CONNECTED)
            return True
        except Exception as exc:
            logger.error("ConsolePublisher '%s' failed to print status: %s", self._name, exc)
            self.metrics.record_failure(str(exc))
            self.set_state(PublisherHealthState.FAILED, str(exc))
            return False

    def publish(self, event: Optional[StandardAnalyticsEvent], serialized_payload: str) -> bool:
        """Fallback for discrete events."""
        if not self._is_running or not self._enabled:
            return False

        if event is not None:
            return self.on_publish_raw("cctv.analytics", "analytics.event", event.to_dict())

        t_start = time.time()
        try:
            print(f"[ConsolePublisher] {serialized_payload}", file=sys.stdout, flush=True)
            self.metrics.record_success((time.time() - t_start) * 1000.0)
            return True
        except Exception as exc:
            self.metrics.record_failure(str(exc))
            return False
