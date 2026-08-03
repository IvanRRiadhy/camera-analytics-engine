"""
Engine Registration Service Component.

Gathers host system information, GPU specifications, CPU specs, and installed vision plugin manifests,
constructing and publishing an EngineRegistrationRequest payload to the message broker during engine boot.
"""

from __future__ import annotations

import logging
import platform
import socket
import time
import uuid
from typing import Any, Optional

import psutil
import torch

from camera_analytics.diagnostics.collector import HardwareDiagnosticCollector

logger = logging.getLogger(__name__)


class EngineRegistrationService:
    """Service gathering hardware specs and plugin metadata to construct and publish registration requests."""

    def __init__(
        self,
        instance_id: str,
        comm_manager: Any,
        plugin_scanner: Optional[Any] = None,
        engine_version: str = "12.6.0",
    ) -> None:
        self.instance_id = instance_id
        self.comm_manager = comm_manager
        self.plugin_scanner = plugin_scanner
        self.engine_version = engine_version
        self.hardware_collector = HardwareDiagnosticCollector()

    def build_registration_payload(self) -> dict[str, Any]:
        """Construct the EngineRegistrationRequest JSON payload.

        Returns:
            Dict payload matching TDS Section 2.1.1 schema.
        """
        sys_metrics = self.hardware_collector.collect_system_metrics()

        gpu_name = "CPU Only"
        cuda_version = "None"
        driver_version = "None"
        total_vram_mb = 0

        if torch.cuda.is_available():
            try:
                gpu_name = torch.cuda.get_device_name(0)
                cuda_version = torch.version.cuda or "Unknown"
                total_vram_mb = torch.cuda.get_device_properties(0).total_memory // (1024 * 1024)
            except Exception:
                pass

        hostname = socket.gethostname()
        try:
            ip_address = socket.gethostbyname(hostname)
        except Exception:
            ip_address = "127.0.0.1"

        installed_plugins = []
        if self.plugin_scanner:
            try:
                plugin_manifests = self.plugin_scanner.scan()
                for manifest in plugin_manifests:
                    installed_plugins.append({
                        "name": getattr(manifest, "name", "unknown"),
                        "version": getattr(manifest, "version", "1.0.0"),
                        "sdk_version": getattr(manifest, "sdk_version", "12.0"),
                        "capabilities": getattr(manifest, "capabilities", []),
                    })
            except Exception as exc:
                logger.warning("Error scanning plugin manifests during registration: %s", exc)

        return {
            "instance_id": self.instance_id,
            "application_id": "00000000-0000-0000-0000-000000000001",
            "worker_node_id": str(uuid.uuid5(uuid.NAMESPACE_DNS, hostname)),
            "hostname": hostname,
            "ip_address": ip_address,
            "os_platform": f"{platform.system()}-{platform.release()}-{platform.machine()}",
            "python_version": platform.python_version(),
            "engine_version": self.engine_version,
            "gpu_info": {
                "device_name": gpu_name,
                "cuda_version": cuda_version,
                "driver_version": driver_version,
                "total_vram_mb": total_vram_mb,
                "cuda_cores": 0,
            },
            "cpu_info": {
                "architecture": platform.machine(),
                "model_name": platform.processor() or "Unknown CPU",
                "total_cores": psutil.cpu_count(logical=False) or 1,
                "total_threads": psutil.cpu_count(logical=True) or 1,
                "total_ram_mb": sys_metrics.get("memory_total_mb", 0),
            },
            "installed_plugins": installed_plugins,
            "registered_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

    def register(self) -> dict[str, Any]:
        """Build registration payload and publish to message broker on `cctv.engine.register`.

        Returns:
            The dispatched registration dictionary payload.
        """
        payload = self.build_registration_payload()
        routing_key = f"engine.register.{self.instance_id}"

        logger.info("Publishing EngineRegistrationRequest for instance '%s' to exchange 'cctv.engine.register'", self.instance_id)

        if hasattr(self.comm_manager, "publish_raw"):
            self.comm_manager.publish_raw("cctv.engine.register", routing_key, payload)
        elif hasattr(self.comm_manager, "publish"):
            self.comm_manager.publish(payload)

        return payload
