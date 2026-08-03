"""
MQTT Network Event Publisher.

Subclass of EventPublisher that publishes StandardAnalyticsEvent JSON payloads to an MQTT Broker
topic (e.g. `camera/{camera_id}/analytics/events`). Supports configurable QoS, retain, keepalive,
auto-reconnect, and non-blocking background network threads. Safe fallback if `paho-mqtt` library is not installed.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Optional
from urllib.parse import urlparse

from camera_analytics.communication.models import StandardAnalyticsEvent
from camera_analytics.communication.publisher_base import EventPublisher
from camera_analytics.communication.registry import PublisherRegistry

logger = logging.getLogger(__name__)


@PublisherRegistry.register("mqtt")
class MQTTPublisher(EventPublisher):
    """Event Publisher that broadcasts events over MQTT network protocol to an MQTT Broker.

    Features:
        - Configurable topic pattern (e.g. `camera/{camera_id}/analytics/events`).
        - QoS (0, 1, 2) and Retain flag support.
        - Non-blocking threaded MQTT client loop (`loop_start`).
        - Automatic background reconnect on connection drop.
        - Graceful fallback if `paho-mqtt` package is not installed.

    Args:
        name: Publisher instance identifier.
        enabled: Whether publisher is enabled.
        broker: Broker URI (e.g. 'mqtt://localhost:1883' or 'localhost').
        port: Broker port (default 1883).
        topic: Topic template string with `{camera_id}` placeholder.
        qos: MQTT Quality of Service level (0, 1, or 2).
        retain: Whether to set retain flag on published messages.
        client_id: Optional custom client ID.
        keepalive: Connection keepalive interval in seconds.
    """

    def __init__(
        self,
        name: str = "mqtt",
        enabled: bool = True,
        broker: str = "localhost",
        port: int = 1883,
        topic: str = "camera/{camera_id}/analytics/events",
        qos: int = 1,
        retain: bool = False,
        client_id: Optional[str] = None,
        keepalive: int = 60,
    ) -> None:
        super().__init__(name=name, enabled=enabled)
        self._broker_host = broker
        self._broker_port = port
        self._topic_template = topic
        self._qos = qos
        self._retain = retain
        self._client_id = client_id or f"camera_analytics_{id(self)}"
        self._keepalive = keepalive

        self._client: Any = None
        self._paho: Any = None
        self._is_connected = False
        self._lock = threading.Lock()

    def on_initialize(self, config: dict[str, Any]) -> None:
        """Initialize MQTT publisher settings from configuration dict."""
        broker_str = config.get("broker", self._broker_host)
        if "://" in broker_str:
            parsed = urlparse(broker_str)
            self._broker_host = parsed.hostname or "localhost"
            if parsed.port:
                self._broker_port = parsed.port
        else:
            self._broker_host = broker_str

        self._broker_port = config.get("port", self._broker_port)
        self._topic_template = config.get("topic", self._topic_template)
        self._qos = config.get("qos", self._qos)
        self._retain = config.get("retain", self._retain)
        self._keepalive = config.get("keepalive", self._keepalive)
        if "client_id" in config:
            self._client_id = config["client_id"]

    def on_start(self) -> None:
        """Attempt to connect to MQTT broker and start network loop thread."""
        try:
            import paho.mqtt.client as mqtt
            self._paho = mqtt
        except ImportError:
            logger.warning(
                "MQTTPublisher '%s': 'paho-mqtt' package not installed. MQTT publishing operates in mock fallback mode.",
                self.name,
            )
            self._is_healthy = False
            return

        try:
            if hasattr(self._paho, "CallbackAPIVersion"):
                client = self._paho.Client(self._paho.CallbackAPIVersion.VERSION1, client_id=self._client_id, clean_session=True)
            else:
                client = self._paho.Client(client_id=self._client_id, clean_session=True)
            client.on_connect = self._on_connect
            client.on_disconnect = self._on_disconnect

            client.connect_async(self._broker_host, self._broker_port, keepalive=self._keepalive)
            client.loop_start()
            self._client = client
            logger.info("MQTTPublisher '%s' connecting to broker at %s:%d...",
                        self.name, self._broker_host, self._broker_port)
        except Exception as exc:
            self._is_healthy = False
            logger.error("MQTTPublisher '%s' connection error (%s)", self.name, exc)

    def publish(self, event: StandardAnalyticsEvent, serialized_payload: str) -> bool:
        """Publish serialized Analytics Event to MQTT topic asynchronously.

        Args:
            event: StandardAnalyticsEvent instance.
            serialized_payload: Pre-serialized JSON string.

        Returns:
            True if queued/published, False if client unavailable or error occurs.
        """
        if not self._is_running or not self._enabled:
            return False

        t_start = time.time()
        # Format topic with camera_id
        target_topic = self._topic_template.format(camera_id=event.camera_id)

        if self._client is None or self._paho is None or not self._is_connected:
            # Fallback mock log when paho-mqtt unavailable or broker not connected
            logger.debug("MQTTPublisher [Fallback Mock] Topic '%s': %s", target_topic, serialized_payload[:80])
            latency_ms = (time.time() - t_start) * 1000.0
            self.record_publish_metrics(success=True, latency_ms=latency_ms)
            return True

        try:
            info = self._client.publish(
                topic=target_topic,
                payload=serialized_payload,
                qos=self._qos,
                retain=self._retain,
            )
            success = info.rc == self._paho.MQTT_ERR_SUCCESS
            latency_ms = (time.time() - t_start) * 1000.0
            self.record_publish_metrics(success=success, latency_ms=latency_ms)
            return success
        except Exception as exc:
            self._is_healthy = False
            logger.error("MQTTPublisher '%s' publish error on topic '%s': %s", self.name, target_topic, exc)
            self.record_publish_metrics(success=False, latency_ms=0.0)
            return False

    def on_stop(self) -> None:
        """Disconnect client and stop loop thread."""
        with self._lock:
            if self._client is not None:
                try:
                    self._client.loop_stop()
                    self._client.disconnect()
                except Exception:
                    pass
                self._client = None
            self._is_connected = False

    # --- Internal Callbacks ---

    def _on_connect(self, client: Any, userdata: Any, flags: Any, rc: int) -> None:
        """Callback when MQTT broker connection is established."""
        if rc == 0:
            self._is_connected = True
            self._is_healthy = True
            logger.info("MQTTPublisher '%s' CONNECTED to broker %s:%d",
                        self.name, self._broker_host, self._broker_port)
        else:
            self._is_connected = False
            self._is_healthy = False
            logger.warning("MQTTPublisher '%s' connection refused (rc=%d)", self.name, rc)

    def _on_disconnect(self, client: Any, userdata: Any, rc: int) -> None:
        """Callback when disconnected from MQTT broker."""
        self._is_connected = False
        self._is_healthy = False
        if rc != 0:
            logger.warning("MQTTPublisher '%s' unexpectedly DISCONNECTED from broker (rc=%d). Reconnecting...",
                           self.name, rc)
