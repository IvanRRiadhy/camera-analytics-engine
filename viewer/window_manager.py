"""
Window Manager Component.

Manages OpenCV live windows, multi-window grid layouts, fullscreen toggles, and hotkeys.
"""

from __future__ import annotations

import logging
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class WindowManager:
    """Manager for OpenCV GUI windows and interactive hotkeys with cursor coordinate tooltips."""

    def __init__(self, window_scale: float = 1.0) -> None:
        self._window_scale = window_scale
        self._open_windows: set[str] = set()
        self._mouse_positions: dict[str, tuple[int, int]] = {}

    def _make_mouse_callback(self, window_title: str):
        def _on_mouse(event: int, x: int, y: int, flags: int, param: Any) -> None:
            if event == cv2.EVENT_MOUSEMOVE:
                self._mouse_positions[window_title] = (x, y)
        return _on_mouse

    def show_frame(self, window_title: str, image: np.ndarray) -> None:
        """Display an image frame in a named window with cursor (x, y) tooltip.

        Args:
            window_title: Window title string.
            image: BGR image array.
        """
        if window_title not in self._open_windows:
            cv2.namedWindow(window_title, cv2.WINDOW_NORMAL)
            cv2.setMouseCallback(window_title, self._make_mouse_callback(window_title))
            self._open_windows.add(window_title)

        canvas = image.copy()

        # Render Cursor Coordinate Tooltip at Top-Right of Cursor
        if window_title in self._mouse_positions:
            mx, my = self._mouse_positions[window_title]
            h, w = canvas.shape[:2]

            if 0 <= mx < w and 0 <= my < h:
                orig_x = int(round(mx / self._window_scale))
                orig_y = int(round(my / self._window_scale))
                coord_text = f"({orig_x}, {orig_y})"

                # Text positioning (top-right of cursor)
                text_x = min(w - 110, mx + 15)
                text_y = max(25, my - 15)

                font = cv2.FONT_HERSHEY_SIMPLEX
                font_scale = 0.55
                thickness = 2
                (t_w, t_h), baseline = cv2.getTextSize(coord_text, font, font_scale, thickness)

                box_x1 = max(0, text_x - 4)
                box_y1 = max(0, text_y - t_h - 4)
                box_x2 = min(w, text_x + t_w + 6)
                box_y2 = min(h, text_y + baseline + 4)

                # Draw dark semi-transparent background box
                overlay = canvas.copy()
                cv2.rectangle(overlay, (box_x1, box_y1), (box_x2, box_y2), (0, 0, 0), -1)
                cv2.addWeighted(overlay, 0.7, canvas, 0.3, 0, canvas)
                cv2.rectangle(canvas, (box_x1, box_y1), (box_x2, box_y2), (0, 255, 255), 1)

                # Render bright yellow (x, y) coordinate text
                cv2.putText(canvas, coord_text, (text_x, text_y), font, font_scale, (0, 255, 255), thickness, cv2.LINE_AA)

                # Small crosshair at cursor center
                cv2.circle(canvas, (mx, my), 3, (0, 255, 255), -1)

        if self._window_scale != 1.0:
            h, w = canvas.shape[:2]
            nw, nh = int(w * self._window_scale), int(h * self._window_scale)
            canvas = cv2.resize(canvas, (nw, nh))

        cv2.imshow(window_title, canvas)

    def process_events(self, delay_ms: int = 1) -> Optional[str]:
        """Poll keyboard events.

        Args:
            delay_ms: Milliseconds delay for waitKey.

        Returns:
            Pressed key string or None.
        """
        key = cv2.waitKey(delay_ms) & 0xFF
        self.last_key = key
        # Keypress processing: ESC or 'q' returns False (signal to exit)
        if key in (27, ord("q"), ord("Q")):
            return False
        elif key == ord("m"):
            return "toggle_metrics"
        elif key == ord("z"):
            return "toggle_zones"
        elif key == ord("s"):
            return "toggle_skeleton"
        return True

    def show_studio_window(self, studio_canvas: np.ndarray, title: str = "AI Engine Development Studio") -> None:
        """Display Engine Studio observability window alongside camera video windows."""
        if title not in self._open_windows:
            cv2.namedWindow(title, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(title, 1024, 600)
            self._open_windows.add(title)
        cv2.imshow(title, studio_canvas)

    def close_all(self) -> None:
        """Destroy all OpenCV windows."""
        if self._open_windows:
            try:
                cv2.destroyAllWindows()
            except Exception:
                pass
            self._open_windows.clear()
            self._mouse_positions.clear()
            logger.info("WindowManager: Closed all GUI windows.")
