"""
OpenCV Studio Renderer Implementation (Sprint H1.5D1).

High-performance OpenCV canvas renderer rendering Pure View Inspector panels onto an image canvas.
"""

from __future__ import annotations

import logging
from typing import Any, Optional
import cv2
import numpy as np

from camera_analytics.studio.renderers.base_renderer import IStudioRenderer
from camera_analytics.studio.snapshot.engine_studio_snapshot import EngineStudioSnapshot

logger = logging.getLogger(__name__)


class OpenCVRenderer(IStudioRenderer):
    """High-performance OpenCV canvas rendering driver for Studio Inspector panels."""

    def __init__(self, width: int = 1024, height: int = 600) -> None:
        self.width = width
        self.height = height

    @property
    def driver_id(self) -> str:
        return "opencv"

    def render(
        self,
        snapshot: EngineStudioSnapshot,
        lines: list[str],
        active_tab_title: str = "Runtime Overview",
    ) -> np.ndarray:
        """Render text lines from a Pure View Inspector panel onto an OpenCV image canvas."""
        canvas = np.zeros((self.height, self.width, 3), dtype=np.uint8)

        # Draw dark Header Bar
        cv2.rectangle(canvas, (0, 0), (self.width, 42), (30, 30, 30), -1)
        cv2.putText(
            canvas,
            f"AI ENGINE STUDIO v2.0 | TAB: [{active_tab_title.upper()}] | SEQ: #{snapshot.sequence_id}",
            (15, 26),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.50,
            (0, 255, 200),
            1,
            cv2.LINE_AA,
        )

        # Draw Hotkey Navigation Sub-Header Bar
        cv2.rectangle(canvas, (0, 42), (self.width, 64), (15, 15, 15), -1)
        nav_str = "NAV: [1:Runtime  2:AI Model  3:Human Track  4:Camera  5:Module  6:Timeline | TAB:Next]"
        cv2.putText(
            canvas,
            nav_str,
            (15, 57),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.38,
            (255, 255, 0),
            1,
            cv2.LINE_AA,
        )

        # Render panel text content
        y0 = 85
        line_height = 19
        for line in lines:
            if y0 > (self.height - 15):
                break

            color = (0, 255, 200) if line.startswith("===") or line.startswith("---") else (
                (255, 255, 255) if line.startswith(" ") and ":" in line else (200, 200, 200)
            )
            cv2.putText(
                canvas,
                line,
                (20, y0),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.43,
                color,
                1,
                cv2.LINE_AA,
            )
            y0 += line_height

        return canvas
