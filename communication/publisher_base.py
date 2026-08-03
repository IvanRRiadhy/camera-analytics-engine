"""
Event Publisher Base Contract & Enterprise Health State Specification.

Defines the abstract base class `EventPublisher` with full lifecycle contracts,
PublisherHealthState enums, standardized operational metrics, exponential backoff retries,
and template `publish_raw()` support.
"""

from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from camera_analytics.communication.models import StandardAnalyticsEvent

logger = logging.getLogger(__name__)


class PublisherHealthState(str, Enum):
    """Standardized lifecycle health states for external publishers."""
    READY = "READY"
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"
    RECONNECTING = "RECONNECTING"
    FAILED = "FAILED"


@dataclass
class PublisherMetrics:
    """Standardized operational performance metrics for publishers."""
    published_count: int = 0
    failed_count: int = 0
    retry_count: int = 0
    total_latency_ms: float = 0.0
    avg_latency_ms: float = 0.0
    last_published_utc: str = ""
    last_error: str = ""

    def record_success(self, latency_ms: float) -> None:
        self.published_count += 1
        self.total_latency_ms += latency_ms
        self.avg_latency_ms = round(self.total_latency_ms / max(1, self.published_count), 2)
        self.last_published_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def record_failure(self, error_msg: str) -> None:
        self.failed_count += 1
        self.last_error = error_msg


class EventPublisher(ABC):
    """Abstract Base Class for all external communication publishers in the platform.

    Provides standard lifecycle management (initialize, start, publish, publish_raw, flush, stop, dispose),
    health state transitions, exponential backoff retries, and metrics tracking.
    """

    def __init__(
        self,
        name: str,
        enabled: bool = True,
        publish_interval_seconds: float = 2.0,
        ignore_change_detection: bool = False,
        **kwargs: Any,
    ) -> None:
        self._name = name
        self._enabled = enabled
        self._is_initialized = False
        self._is_running = False
        self._state = PublisherHealthState.READY
        self.metrics = PublisherMetrics()

        # Per-Publisher Interval & Change Detection Attributes
        self.publish_interval_seconds: float = float(publish_interval_seconds)
        self.ignore_change_detection: bool = bool(ignore_change_detection)
        self._last_published_times: Dict[str, float] = {}
        self._last_published_signatures: Dict[str, str] = {}

        # Retry & Exponential Backoff Configuration
        self._max_retries = 3
        self._min_backoff_sec = 1.0
        self._max_backoff_sec = 16.0
        self._backoff_multiplier = 2.0

    @property
    def name(self) -> str:
        """Publisher identifier name."""
        return self._name

    @property
    def is_enabled(self) -> bool:
        """Whether the publisher is enabled in configuration."""
        return self._enabled

    @property
    def is_initialized(self) -> bool:
        """Whether the publisher has been initialized."""
        return self._is_initialized

    @property
    def is_running(self) -> bool:
        """Whether the publisher is actively running."""
        return self._is_running

    @property
    def state(self) -> PublisherHealthState:
        """Current publisher health state."""
        return self._state

    def set_state(self, state: PublisherHealthState, reason: str = "") -> None:
        """Transition publisher health state."""
        if self._state != state:
            logger.info("Publisher '%s' state transition: %s -> %s %s", 
                        self._name, self._state.value, state.value, f"({reason})" if reason else "")
            self._state = state

    def get_health(self) -> Dict[str, Any]:
        """Get publisher health status and operational metrics."""
        return {
            "name": self._name,
            "enabled": self._enabled,
            "running": self._is_running,
            "state": self._state.value,
            "published_count": self.metrics.published_count,
            "failed_count": self.metrics.failed_count,
            "retry_count": self.metrics.retry_count,
            "avg_latency_ms": self.metrics.avg_latency_ms,
            "last_published_utc": self.metrics.last_published_utc,
            "last_error": self.metrics.last_error,
            "publish_interval_seconds": self.publish_interval_seconds,
            "ignore_change_detection": self.ignore_change_detection,
        }

    # --- Lifecycle Contracts ---

    def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize publisher with configuration dictionary."""
        if self._is_initialized:
            return

        self._max_retries = config.get("max_retries", self._max_retries)
        self._min_backoff_sec = config.get("min_backoff_sec", self._min_backoff_sec)
        self._max_backoff_sec = config.get("max_backoff_sec", self._max_backoff_sec)
        self._backoff_multiplier = config.get("backoff_multiplier", self._backoff_multiplier)

        # Parse Per-Publisher Interval & Change Detection Policy
        self.publish_interval_seconds = float(config.get("publish_interval_seconds", self.publish_interval_seconds))
        self.ignore_change_detection = bool(config.get("ignore_change_detection", self.ignore_change_detection))

        self.on_initialize(config)
        self._is_initialized = True
        self.set_state(PublisherHealthState.READY, "Initialized")
        logger.debug("EventPublisher '%s' initialized (interval=%.1fs, ignore_change_detection=%s)",
                     self._name, self.publish_interval_seconds, self.ignore_change_detection)

    def start(self) -> None:
        """Start the publisher background client or file stream."""
        if not self._is_initialized:
            raise RuntimeError(f"Cannot start EventPublisher '{self._name}': not initialized.")
        if self._is_running or not self._enabled:
            return
        self.on_start()
        self._is_running = True
        self.set_state(PublisherHealthState.CONNECTED, "Started")
        logger.debug("EventPublisher '%s' started", self._name)

    @abstractmethod
    def publish(self, event: StandardAnalyticsEvent, serialized_payload: str) -> bool:
        """Publish discrete analytics event payload. Concrete subclasses must implement."""
        pass

    def _compute_snapshot_signature(self, payload_dict: Dict[str, Any]) -> str:
        """Compute lightweight signature string for Change Detection."""
        plugins = payload_dict.get("plugins", {})
        return json.dumps(plugins, sort_keys=True)

    def publish_raw(self, exchange: str, routing_key: str, payload_dict: Dict[str, Any]) -> bool:
        """Publish raw payload dictionary with per-publisher interval & independent change detection evaluation."""
        if not self._is_running or not self._enabled:
            return False

        camera_id = str(payload_dict.get("cameraId", "default_camera"))
        now = time.time()

        # 1. Per-Publisher Interval Check
        last_pub_time = self._last_published_times.get(camera_id, 0.0)
        if (now - last_pub_time) < self.publish_interval_seconds:
            return False

        # 2. Independent Change Detection Check
        if not self.ignore_change_detection:
            sig = self._compute_snapshot_signature(payload_dict)
            last_sig = self._last_published_signatures.get(camera_id, "")
            if sig == last_sig:
                return False
            self._last_published_signatures[camera_id] = sig

        try:
            res = self.on_publish_raw(exchange, routing_key, payload_dict)
            if res:
                self._last_published_times[camera_id] = now
            return res
        except Exception as exc:
            logger.error("Publisher '%s' publish_raw error: %s", self._name, exc)
            self.metrics.record_failure(str(exc))
            return False

    def on_publish_raw(self, exchange: str, routing_key: str, payload_dict: Dict[str, Any]) -> bool:
        """Default hook fallback: converts dict payload to JSON string and calls publish()."""
        json_str = json.dumps(payload_dict, separators=(",", ":"))
        return self.publish(event=None, serialized_payload=json_str)

    def execute_with_retry(self, operation: Any, *args: Any, **kwargs: Any) -> bool:
        """Execute a publishing operation with exponential backoff retries and randomized jitter."""
        import random

        attempt = 0
        backoff = self._min_backoff_sec

        while attempt < self._max_retries:
            try:
                t_start = time.time()
                res = operation(*args, **kwargs)
                if res:
                    latency = (time.time() - t_start) * 1000.0
                    self.metrics.record_success(latency)
                    self.set_state(PublisherHealthState.CONNECTED)
                    return True
            except Exception as exc:
                attempt += 1
                self.metrics.retry_count += 1
                self.metrics.record_failure(str(exc))
                self.set_state(PublisherHealthState.RECONNECTING, f"Attempt {attempt}/{self._max_retries}: {exc}")

                jitter = random.uniform(0.0, 0.5)
                sleep_time = backoff + jitter
                logger.warning("Publisher '%s' retry %d/%d failed (%s). Sleeping %.2fs (jitter: %.2f)...",
                               self._name, attempt, self._max_retries, exc, sleep_time, jitter)
                time.sleep(sleep_time)
                backoff = min(self._max_backoff_sec, backoff * self._backoff_multiplier)

        self.set_state(PublisherHealthState.FAILED, "Max retries exceeded")
        return False

    def stop(self) -> None:
        """Stop background publisher loop or connection."""
        if not self._is_running:
            return
        self.on_stop()
        self._is_running = False
        self.set_state(PublisherHealthState.DISCONNECTED, "Stopped")
        logger.debug("EventPublisher '%s' stopped", self._name)

    def dispose(self) -> None:
        """Dispose publisher resources."""
        self.stop()
        self.on_dispose()
        self._is_initialized = False
        logger.debug("EventPublisher '%s' disposed", self._name)

    # --- Virtual Lifecycle Hooks ---
    def on_initialize(self, config: Dict[str, Any]) -> None: pass
    def on_start(self) -> None: pass
    def on_stop(self) -> None: pass
    def on_dispose(self) -> None: pass
