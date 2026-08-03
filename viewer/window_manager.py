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
    """Manager for OpenCV GUI windows and interactive hotkeys."""

    def __init__(self, window_scale: float = 1.0) -> None:
        self._window_scale = window_scale
        self._open_windows: set[str] = set()

    def show_frame(self, window_title: str, image: np.ndarray) -> None:
        """Display an image frame in a named window.

        Args:
            window_title: Window title string.
            image: BGR image array.
        """
        if window_title not in self._open_windows:
            cv2.namedWindow(window_title, cv2.WINDOW_NORMAL)
            self._open_windows.add(window_title)

        if self._window_scale != 1.0:
            h, w = image.shape[:2]
            nw, nh = int(w * self._window_scale), int(h * self._window_scale)
            image = cv2.resize(image, (nw, nh))

        cv2.imshow(window_title, image)

    def process_events(self, delay_ms: int = 1) -> Optional[str]:
        """Poll keyboard events.

        Args:
            delay_ms: Milliseconds delay for waitKey.

        Returns:
            Pressed key string or None.
        """
        key = cv2.waitKey(delay_ms) & 0xFF
        if key == 27 or key == ord("q"):
            return "quit"
        elif key == ord("m"):
            return "toggle_metrics"
        elif key == ord("z"):
            return "toggle_zones"
        elif key == ord("s"):
            return "toggle_skeleton"
        return None

    def close_all(self) -> None:
        """Destroy all OpenCV windows."""
        if self._open_windows:
            try:
                cv2.destroyAllWindows()
            except Exception:
                pass
            self._open_windows.clear()
            logger.info("WindowManager: Closed all GUI windows.")
