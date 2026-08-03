"""
REST HTTP Webhook Publisher Implementation.

Publishes `StandardAnalyticsEvent` objects to configured HTTP REST Webhook endpoints
with support for custom headers, authentication tokens, timeout, and exponential backoff retries.
"""

from __future__ import annotations

import logging
import time
import urllib.error
import urllib.request
from typing import Any, Optional

from camera_analytics.communication.models import StandardAnalyticsEvent
from camera_analytics.communication.publisher_base import EventPublisher
from camera_analytics.communication.registry import register_publisher

logger = logging.getLogger(__name__)


@register_publisher("rest")
class RestPublisher(EventPublisher):
    """Event Publisher that sends POST requests to REST Webhook endpoints."""

    def __init__(
        self,
        name: str = "rest_publisher",
        enabled: bool = True,
        endpoint_url: str = "http://localhost:8000/api/v1/events",
        headers: Optional[dict[str, str]] = None,
        timeout_sec: float = 3.0,
        max_retries: int = 3,
    ) -> None:
        super().__init__(name=name, enabled=enabled)
        self._endpoint_url = endpoint_url
        self._headers = headers or {"Content-Type": "application/json"}
        self._timeout_sec = timeout_sec
        self._max_retries = max_retries

    def on_initialize(self, config: dict[str, Any]) -> None:
        """Initialize RestPublisher configuration."""
        self._endpoint_url = config.get("endpoint_url", self._endpoint_url)
        self._timeout_sec = float(config.get("timeout_sec", self._timeout_sec))
        self._max_retries = int(config.get("max_retries", self._max_retries))
        if "headers" in config and isinstance(config["headers"], dict):
            self._headers.update(config["headers"])

    def publish(self, event: StandardAnalyticsEvent, serialized_payload: str) -> bool:
        """Publish event payload via HTTP POST with exponential backoff retries."""
        if not self._is_running or not self._enabled:
            return False

        data_bytes = serialized_payload.encode("utf-8")
        req = urllib.request.Request(
            url=self._endpoint_url,
            data=data_bytes,
            headers=self._headers,
            method="POST",
        )

        retries = 0
        backoff_sec = 0.1

        while retries <= self._max_retries:
            t_start = time.time()
            try:
                with urllib.request.urlopen(req, timeout=self._timeout_sec) as response:
                    if 200 <= response.status < 300:
                        latency_ms = (time.time() - t_start) * 1000.0
                        self.record_publish_metrics(success=True, latency_ms=latency_ms, retries=retries)
                        return True
            except Exception as exc:
                retries += 1
                if retries > self._max_retries:
                    logger.warning(
                        "RestPublisher '%s' failed POST to '%s' after %d retries: %s",
                        self._name,
                        self._endpoint_url,
                        retries - 1,
                        exc,
                    )
                    self.record_publish_metrics(success=False, latency_ms=0.0, retries=retries - 1)
                    return False
                time.sleep(backoff_sec)
                backoff_sec *= 2.0

        return False
