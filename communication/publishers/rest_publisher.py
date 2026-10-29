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
        raw_endpoint_url: Optional[str] = None,
        headers: Optional[dict[str, str]] = None,
        timeout_sec: float = 3.0,
        max_retries: int = 3,
    ) -> None:
        super().__init__(name=name, enabled=enabled)
        self._endpoint_url = endpoint_url
        self._raw_endpoint_url = raw_endpoint_url or endpoint_url
        self._headers = headers or {"Content-Type": "application/json"}
        self._timeout_sec = timeout_sec
        self._max_retries = max_retries

    def on_initialize(self, config: dict[str, Any]) -> None:
        """Initialize RestPublisher configuration."""
        self._endpoint_url = config.get("endpoint_url", self._endpoint_url)
        self._raw_endpoint_url = config.get("raw_endpoint_url", self._raw_endpoint_url or self._endpoint_url)
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
                        self.metrics.record_success(latency_ms)
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
                    self.metrics.record_failure(str(exc))
                    return False
                time.sleep(backoff_sec)
                backoff_sec *= 2.0

        return False

    def on_publish_raw(self, exchange: str, routing_key: str, payload_dict: dict[str, Any]) -> bool:
        """Publish raw payload dictionary (heartbeat, registration, snapshot) via HTTP POST."""
        if not self._is_running or not self._enabled:
            return False

        import json
        json_str = json.dumps(payload_dict, separators=(",", ":"))
        data_bytes = json_str.encode("utf-8")

        target_url = self._raw_endpoint_url
        req = urllib.request.Request(
            url=target_url,
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
                        self.metrics.record_success(latency_ms)
                        return True
            except Exception as exc:
                retries += 1
                if retries > self._max_retries:
                    logger.warning(
                        "RestPublisher '%s' failed raw POST to '%s' after %d retries: %s",
                        self._name,
                        target_url,
                        retries - 1,
                        exc,
                    )
                    self.metrics.record_failure(str(exc))
                    return False
                time.sleep(backoff_sec)
                backoff_sec *= 2.0

        return False
