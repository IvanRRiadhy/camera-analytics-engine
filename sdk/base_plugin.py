import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Optional

from camera_analytics.events.bus import RuntimeEventBus
from camera_analytics.events.models import BaseRuntimeEvent
from camera_analytics.plugins.framework.context import PluginContext
from camera_analytics.plugins.framework.states import PluginState

logger = logging.getLogger(__name__)


class BaseAnalyticsPlugin(ABC):
    """Abstract Base Class for all vision analytics plugins in the framework.

    Plugins inherit from this base class and implement frame processing, warmup,
    and lifecycle event callbacks.
    """

    def __init__(self, name: str, version: str = "1.0.0", description: str = "") -> None:
        self.name = name
        self.version = version
        self.description = description
        self.state: PluginState = PluginState.INSTALLED
        self.context: Optional[PluginContext] = None

        # Runtime Metrics
        self.frames_processed: int = 0
        self.events_generated: int = 0
        self.errors: int = 0
        self.warnings: int = 0
        self.last_inference_time_ms: float = 0.0
        self.total_inference_time_ms: float = 0.0

    def emit(self, event: BaseRuntimeEvent) -> None:
        """Emit a strongly typed runtime event over the unified RuntimeEventBus."""
        event.plugin_name = self.name
        if self.context and hasattr(self.context, "publish"):
            self.context.publish(event)
        else:
            RuntimeEventBus.get_instance().publish(event)

    def initialize(self, context: PluginContext) -> bool:
        """Initialize plugin with injected runtime context."""
        self.context = context
        self.state = PluginState.INITIALIZED
        logger.info("[Plugin:%s] Initialized successfully in pipeline '%s'.", self.name, context.pipeline_id)
        return True

    def warmup(self) -> bool:
        """Execute model warmup / tensor allocation before processing live stream."""
        self.state = PluginState.WARMUP
        time.sleep(0.01) # Simulate hardware warmup
        logger.info("[Plugin:%s] Warmup complete.", self.name)
        return True

    def start(self) -> None:
        """Start active execution state."""
        self.state = PluginState.RUNNING
        logger.info("[Plugin:%s] State transitioned to RUNNING.", self.name)

    def process(self, context: Any) -> list[BaseRuntimeEvent]:
        """Process unified SharedAnalyticsContext containing pre-computed detections & tracks.

        Must be implemented by concrete vision analytics plugins.
        """
        return []

    def process_frame(self, frame: Any, metadata: Optional[dict[str, Any]] = None) -> list[Any]:
        """Legacy process_frame entry point wrapped for backwards compatibility."""
        from camera_analytics.context.unified_context import SharedAnalyticsContext
        ctx = SharedAnalyticsContext(frame=frame, metadata=metadata or {})
        return self.process(ctx)

    def on_event(self, event: Any) -> None:
        """Handle incoming spatial or track events."""
        pass

    def stop(self) -> None:
        """Transition plugin to STOPPING / STOPPED state."""
        self.state = PluginState.STOPPING
        logger.info("[Plugin:%s] Stopping...", self.name)
        self.state = PluginState.STOPPED

    def shutdown(self) -> None:
        """Release CUDA memory and plugin resources."""
        self.stop()
        logger.info("[Plugin:%s] Shutdown complete.", self.name)
