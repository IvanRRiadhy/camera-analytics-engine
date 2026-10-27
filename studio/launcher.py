"""
StudioLauncher LifeCycle Manager (Sprint H1.5D1.6).

Manages the initialization, refresh loop updates, telemetry snapshot collection,
and shutdown of the AI Engine Development Studio.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import numpy as np

from camera_analytics.studio.coordinator import EngineStudioCoordinator
from camera_analytics.studio.inspectors.model_inspector import AIModelInspector
from camera_analytics.studio.inspectors.camera_inspector import CameraInspector
from camera_analytics.studio.inspectors.event_timeline import EventTimelineInspector
from camera_analytics.studio.inspectors.human_runtime import HumanRuntimeInspector
from camera_analytics.studio.inspectors.pipeline_graph import PipelineGraphInspector
from camera_analytics.studio.inspectors.runtime_overview import RuntimeOverviewInspector
from camera_analytics.studio.plugins.plugin_registry import PluginRegistry
from camera_analytics.studio.renderers.opencv_renderer import OpenCVRenderer
from camera_analytics.studio.scheduler import AdaptiveRefreshMode, RefreshScheduler
from camera_analytics.viewer.window_manager import WindowManager

logger = logging.getLogger(__name__)


from camera_analytics.studio.layout_manager import StudioLayoutManager


class StudioLauncher:
    """Decoupled launcher managing Studio initialization, refresh loop, and rendering."""

    def __init__(self, config: Optional[dict[str, Any]] = None) -> None:
        self.config = config or {}
        self.enabled = self.config.get("enabled", True)
        self.coordinator: Optional[EngineStudioCoordinator] = None
        self.layout_manager: StudioLayoutManager = StudioLayoutManager()
        self.renderer: Optional[OpenCVRenderer] = None
        self.scheduler: Optional[RefreshScheduler] = None
        self.window_title: str = "AI Engine Development Studio"
        self._is_initialized: bool = False

    def initialize(self) -> None:
        """Initialize EngineStudioCoordinator, InspectorRegistry, StudioLayoutManager, and OpenCVRenderer."""
        if not self.enabled or self._is_initialized:
            return

        timeout_ms = float(self.config.get("collector_timeout_ms", 100.0))
        self.coordinator = EngineStudioCoordinator(collector_timeout_ms=timeout_ms)
        self.layout_manager.set_inspectors(self.coordinator.inspectors)
        self.scheduler = RefreshScheduler(default_mode=AdaptiveRefreshMode.DEBUG)
        self.renderer = OpenCVRenderer(width=1024, height=600)

        self._is_initialized = True
        logger.info("[StudioLauncher] AI Engine Development Studio initialized successfully with 6 Inspectors & LayoutManager.")

    def handle_key(self, key_code: int) -> bool:
        """Forward keyboard input to StudioLayoutManager for tab navigation."""
        if not self.enabled or not self._is_initialized:
            return False
        return self.layout_manager.handle_key(key_code)

    def update_and_render(
        self,
        window_manager: WindowManager,
        execution_workers: Optional[list[Any]] = None,
        context: Optional[Any] = None,
    ) -> None:
        """Collect telemetry, generate EngineStudioSnapshot, render active inspector tab, and display studio window."""
        if not self.enabled or not self._is_initialized or self.coordinator is None or self.renderer is None:
            return

        # 1. Populate CollectorContext from live engine state
        if execution_workers:
            active_cams = []
            for ew in execution_workers:
                cam_id = getattr(ew, "camera_id", "cam_unknown")
                active_cams.append(cam_id)
            self.coordinator.context.active_camera_ids = active_cams

        if context is not None:
            self.coordinator.context.custom_context["context"] = context
            if hasattr(context, "pipelines"):
                self.coordinator.context.pipelines = context.pipelines
            if hasattr(context, "model_manager"):
                self.coordinator.context.model_manager = context.model_manager
            if hasattr(context, "scheduler"):
                self.coordinator.context.scheduler = context.scheduler

        # 2. Generate immutable telemetry snapshot via EngineStudioCoordinator
        snapshot = self.coordinator.generate_snapshot()

        # 3. Retrieve lines from active Pure View Inspector Panel managed by StudioLayoutManager
        active_insp = self.layout_manager.active_inspector
        if active_insp and hasattr(active_insp, "render_text"):
            lines = active_insp.render_text(snapshot)
            tab_title = self.layout_manager.active_tab_title
        else:
            lines = ["Inspector not available."]
            tab_title = "Unknown"

        # 4. Render canvas via Studio OpenCVRenderer
        canvas = self.renderer.render(snapshot, lines, active_tab_title=tab_title)

        # 5. Display in OpenCV Window via WindowManager
        window_manager.show_studio_window(canvas, title=self.window_title)

    def shutdown(self) -> None:
        """Shutdown Studio resources."""
        self._is_initialized = False
        logger.info("[StudioLauncher] Studio shutdown complete.")
