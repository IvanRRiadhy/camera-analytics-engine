"""
Engine Heartbeat Service Component.

Runs a non-blocking daemon thread loop emitting periodic 5-second telemetry heartbeat messages
containing CPU/GPU metrics, active stream telemetry, and service runtime health.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Optional

from camera_analytics.diagnostics.collector import HardwareDiagnosticCollector

logger = logging.getLogger(__name__)


class EngineHeartbeatService:
    """Service broadcasting periodic telemetry heartbeats over message broker."""

    def __init__(
        self,
        instance_id: str,
        comm_manager: Any,
        pipeline_coordinator: Optional[Any] = None,
        service_runtime: Optional[Any] = None,
        interval_sec: float = 5.0,
    ) -> None:
        self.instance_id = instance_id
        self.comm_manager = comm_manager
        self.pipeline_coordinator = pipeline_coordinator
        self.service_runtime = service_runtime
        self.interval_sec = interval_sec
        self.collector = HardwareDiagnosticCollector()
        self.sequence_number = 0
        self._thread: Optional[threading.Thread] = None
        self._is_running = False

    def start(self) -> None:
        """Start the background heartbeat emission thread loop."""
        if self._is_running:
            return
        self._is_running = True
        self._thread = threading.Thread(target=self._heartbeat_loop, daemon=True, name="EngineHeartbeat")
        self._thread.start()
        logger.info("EngineHeartbeatService started (interval=%.1fs)", self.interval_sec)

    def _heartbeat_loop(self) -> None:
        """Background thread loop emitting heartbeats every interval_sec seconds."""
        while self._is_running:
            try:
                self.sequence_number += 1
                sys_metrics = self.collector.collect_system_metrics()

                pipelines_telemetry: list[dict[str, Any]] = []
                if self.pipeline_coordinator and hasattr(self.pipeline_coordinator, "get_telemetry"):
                    try:
                        pipelines_telemetry = self.pipeline_coordinator.get_telemetry()
                    except Exception as exc:
                        logger.warning("Error collecting pipeline telemetry for heartbeat: %s", exc)

                svc_status = "HEALTHY"
                running_svcs: list[str] = []
                err_count = 0
                if self.service_runtime:
                    try:
                        svc_status = getattr(self.service_runtime, "status", "HEALTHY")
                        running_svcs = getattr(self.service_runtime, "active_services", [])
                    except Exception:
                        pass

                payload = {
                    "instance_id": self.instance_id,
                    "application_id": "00000000-0000-0000-0000-000000000001",
                    "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "sequence_number": self.sequence_number,
                    "system_metrics": sys_metrics,
                    "pipelines": pipelines_telemetry,
                    "service_runtime": {
                        "status": str(svc_status),
                        "running_services": running_svcs,
                        "error_count": err_count,
                    },
                }

                routing_key = f"engine.heartbeat.{self.instance_id}"
                if hasattr(self.comm_manager, "publish_raw"):
                    self.comm_manager.publish_raw("cctv.engine.heartbeat", routing_key, payload)
                elif hasattr(self.comm_manager, "publish"):
                    self.comm_manager.publish(payload)
            except Exception as exc:
                logger.error("EngineHeartbeatService error during loop: %s", exc)

            # Sleep in short increments to allow rapid shutdown response
            slept = 0.0
            while self._is_running and slept < self.interval_sec:
                time.sleep(0.1)
                slept += 0.1

    def stop(self) -> None:
        """Stop the background heartbeat emission thread loop."""
        self._is_running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        logger.info("EngineHeartbeatService stopped")
