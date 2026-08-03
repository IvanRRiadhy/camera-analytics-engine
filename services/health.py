"""
Hierarchical Health Monitoring Subsystem.

Aggregates health states across Runtime, Service, and Plugin tiers.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from camera_analytics.services.lifecycle import ServiceLifecycleState
from camera_analytics.services.registry import ServiceRegistry

logger = logging.getLogger(__name__)


class HierarchicalHealthMonitor:
    """Aggregates Health Hierarchy: Runtime ➔ Service ➔ Plugin."""

    def __init__(self, registry: ServiceRegistry) -> None:
        self.registry = registry
        self.start_time = time.time()

    def get_health_hierarchy(self) -> dict[str, Any]:
        """Generate hierarchical health report."""
        entries = self.registry.list_services()

        running_services = [e for e in entries if e.state == ServiceLifecycleState.RUNNING]
        failed_services = [e for e in entries if e.state == ServiceLifecycleState.FAILED]

        uptime_sec = time.time() - self.start_time

        plugins_health: dict[str, Any] = {}
        for entry in entries:
            manifest = entry.manifest
            plugins_health[manifest.service_name] = {
                "version": manifest.version,
                "state": entry.state.value,
                "enabled": manifest.enabled,
                "execution_mode": manifest.execution_mode,
                "error_count": entry.error_count,
                "last_error": entry.last_error,
                "capabilities": manifest.capabilities,
                "dependencies": manifest.dependencies,
            }

        runtime_healthy = len(failed_services) == 0 and len(entries) > 0

        return {
            "runtime": {
                "status": "HEALTHY" if runtime_healthy else "DEGRADED",
                "uptime_sec": round(uptime_sec, 1),
                "total_services": len(entries),
                "running_services": len(running_services),
                "failed_services": len(failed_services),
            },
            "services": plugins_health,
        }
