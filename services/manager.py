"""
Event Service Runtime Manager.

Top-level orchestrator responsible for plugin discovery, topological startup, runtime management,
event dispatching, and health reporting.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from camera_analytics.communication.models import StandardAnalyticsEvent
from camera_analytics.eventing.event_bus import PlatformEventBus
from camera_analytics.eventing.models import PlatformEvent
from camera_analytics.services.discovery import ServiceDiscovery
from camera_analytics.services.runtime import EventServiceRuntime

logger = logging.getLogger(__name__)


class EventServiceRuntimeManager:
    """Top-Level Orchestrator for Event Service Runtime."""

    def __init__(
        self,
        plugin_dir: str | Path = "camera_analytics/services/plugins",
        event_bus: Optional[PlatformEventBus] = None,
        config: Optional[dict[str, Any]] = None,
    ) -> None:
        self.plugin_dir = Path(plugin_dir).resolve()
        self.event_bus = event_bus or PlatformEventBus()
        self.config = config or {}
        self.runtime = EventServiceRuntime(event_bus=self.event_bus)
        self.discovery = ServiceDiscovery(search_dir=self.plugin_dir)

    def initialize_and_start(self) -> int:
        """Discover, load, and start all event services in topological order.

        Returns:
            Number of successfully loaded services.
        """
        discovered = self.discovery.discover_manifests()
        loaded_count = 0

        for s_name, (manifest, plugin_folder) in discovered.items():
            s_config = self.config.get("services", {}).get(s_name, {})
            # Check if dynamically enabled/disabled in config
            if "enabled" in s_config:
                manifest.enabled = s_config["enabled"]

            if manifest.enabled:
                ok = self.runtime.load_and_initialize_service(manifest, plugin_folder, s_config)
                if ok:
                    loaded_count += 1

        self.runtime.start_all_services()
        logger.info("EventServiceRuntimeManager initialized and started %d services", loaded_count)
        return loaded_count

    def dispatch(self, event: StandardAnalyticsEvent | PlatformEvent) -> int:
        """Dispatch event through runtime kernel."""
        return self.runtime.process_event(event)

    def get_health_report(self) -> dict[str, Any]:
        """Get hierarchical health report."""
        return self.runtime.health_monitor.get_health_hierarchy()

    def shutdown(self) -> None:
        """Shutdown service runtime gracefully."""
        self.runtime.stop_all_services()
