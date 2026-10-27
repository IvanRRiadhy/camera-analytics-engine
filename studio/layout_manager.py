"""
Studio Layout Manager Component (Sprint H1.5D1.6C).

Manages Studio layout tree, inspector tab list, active inspector selection,
and keyboard navigation (keys 1-6, Tab, Shift+Tab), eliminating legacy render paths.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class StudioLayoutManager:
    """Manages active tab selection, keyboard navigation, and inspector rendering delegation."""

    TAB_KEY_MAP = {
        ord("1"): 0,  # Runtime Overview
        ord("2"): 1,  # AI Model Inspector
        ord("3"): 2,  # Human Runtime Inspector
        ord("4"): 3,  # Camera Inspector
        ord("5"): 4,  # Module Inspector
        ord("6"): 5,  # Event Timeline Inspector
    }

    def __init__(self) -> None:
        self._active_index: int = 0
        self._inspectors: list[Any] = []

    def set_inspectors(self, inspectors: list[Any]) -> None:
        """Register persistent list of inspector instances from EngineStudioCoordinator."""
        self._inspectors = list(inspectors)
        if self._active_index >= len(self._inspectors):
            self._active_index = 0

    @property
    def active_inspector(self) -> Optional[Any]:
        """Return the currently selected active inspector instance."""
        if 0 <= self._active_index < len(self._inspectors):
            return self._inspectors[self._active_index]
        return None

    @property
    def active_index(self) -> int:
        return self._active_index

    @property
    def active_tab_title(self) -> str:
        active = self.active_inspector
        if active and hasattr(active, "title"):
            return active.title
        return "Runtime Overview"

    def handle_key(self, key_code: int) -> bool:
        """Process keyboard shortcut for tab switching.
        
        Returns:
            True if key event changed active tab index, False otherwise.
        """
        if key_code in self.TAB_KEY_MAP:
            target_idx = self.TAB_KEY_MAP[key_code]
            if target_idx < len(self._inspectors):
                self._active_index = target_idx
                logger.info("[StudioLayoutManager] Switched active tab to index %d (%s)", self._active_index, self.active_tab_title)
                return True

        # Tab / Next Tab (9 is ASCII Tab)
        if key_code == 9 or key_code == ord("\t"):
            if self._inspectors:
                self._active_index = (self._active_index + 1) % len(self._inspectors)
                logger.info("[StudioLayoutManager] Tab key pressed -> Active tab %d (%s)", self._active_index, self.active_tab_title)
                return True

        # Backspace / 'b' for Previous Tab
        if key_code == ord("b") or key_code == ord("B"):
            if self._inspectors:
                self._active_index = (self._active_index - 1) % len(self._inspectors)
                logger.info("[StudioLayoutManager] Prev key pressed -> Active tab %d (%s)", self._active_index, self.active_tab_title)
                return True

        return False
