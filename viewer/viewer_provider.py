"""
Viewer Provider Component.

Extends OutputProvider interface to present live camera streams using OverlayRenderer & WindowManager.
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np

from camera_analytics.communication.models import StandardAnalyticsEvent
from camera_analytics.ingestion.models import IngestedFrame
from camera_analytics.output.base import OutputProvider
from camera_analytics.viewer.builder import FramePresentationBuilder
from camera_analytics.viewer.models import FramePresentation, OverlayData
from camera_analytics.viewer.renderer import OverlayRenderer
from camera_analytics.viewer.window_manager import WindowManager

logger = logging.getLogger(__name__)


class ViewerProvider(OutputProvider):
    """OutputProvider rendering live stream presentations via WindowManager."""

    def __init__(
        self,
        name: str = "opencv_viewer",
        window_scale: float = 1.0,
        enabled: bool = True,
    ) -> None:
        super().__init__(name=name, enabled=enabled)
        self._window_manager = WindowManager(window_scale=window_scale)
        self._renderer = OverlayRenderer()

    @property
    def window_manager(self) -> WindowManager:
        return self._window_manager

    @property
    def renderer(self) -> OverlayRenderer:
        return self._renderer

    def render_presentation(self, presentation: FramePresentation) -> np.ndarray:
        """Render presentation view model onto image array.

        Args:
            presentation: FramePresentation view model.

        Returns:
            Rendered NumPy BGR image array.
        """
        rendered_image = self._renderer.render(presentation)
        self._window_manager.show_frame(presentation.camera_name, rendered_image)
        return rendered_image

    def render_decoupled(
        self,
        camera_name: str,
        raw_frame: IngestedFrame,
        overlay: Optional[OverlayData],
        max_age_ms: float = 500.0,
    ) -> np.ndarray:
        """Render decoupled raw frame with separate latest overlay.

        Args:
            camera_name: Display name of the camera window.
            raw_frame: IngestedFrame containing the newest ingested image.
            overlay: Latest OverlayData published by execution worker, or None.
            max_age_ms: Max overlay age before suppressing stale boxes.

        Returns:
            Rendered NumPy BGR image array.
        """
        if overlay is not None:
            age_ms = max(0.0, (raw_frame.timestamp - overlay.timestamp) * 1000.0)
            is_stale = (age_ms > max_age_ms)
        else:
            is_stale = True
            age_ms = 0.0

        rendered_image = self._renderer.render(
            presentation_or_frame=raw_frame.image,
            overlay=overlay,
            is_stale=is_stale,
            stale_age_ms=age_ms,
            max_age_ms=max_age_ms,
            camera_name=camera_name,
        )
        self._window_manager.show_frame(camera_name, rendered_image)
        return rendered_image

    def output(self, event: StandardAnalyticsEvent) -> bool:
        """Process analytics event (no-op for viewer provider)."""
        return True

    def flush(self) -> None:
        """Flush window manager."""
        pass

    def close(self) -> None:
        """Close GUI windows."""
        self._window_manager.close_all()
