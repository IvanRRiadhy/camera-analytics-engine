import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from camera_analytics.events.bus import RuntimeEventBus
from camera_analytics.events.models import BaseRuntimeEvent


@dataclass
class PluginContext:
    """Runtime context injected into analytics plugins during initialization."""

    pipeline_id: str
    camera_id: str
    engine_instance_id: str = "engine_edge_01"
    camera_name: str = "CAM-01 Main Lobby"
    rtsp_url: str = "rtsp://admin:Admin1234@192.168.1.64/Streaming/channels/2"
    config: dict[str, Any] = field(default_factory=dict)
    publisher: Any = None
    event_bus: Optional[RuntimeEventBus] = field(default_factory=RuntimeEventBus.get_instance)
    logger: logging.Logger = field(default_factory=lambda: logging.getLogger("PluginContext"))
    telemetry_collector: Any = None

    def publish(self, event: BaseRuntimeEvent) -> None:
        """Publish a strongly typed runtime event over the unified Event Bus."""
        if self.event_bus:
            self.event_bus.publish(event)
