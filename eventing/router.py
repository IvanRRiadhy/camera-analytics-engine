"""
Platform Event Router.

Filters and routes PlatformEvent instances based on rules, topics, or versions.
"""

from __future__ import annotations

import logging
from typing import Callable, Optional

from camera_analytics.eventing.models import PlatformEvent

logger = logging.getLogger(__name__)


class PlatformEventRouter:
    """Evaluates filter conditions to route PlatformEvents to target handlers."""

    def __init__(self) -> None:
        self._rules: list[tuple[Callable[[PlatformEvent], bool], Callable[[PlatformEvent], None]]] = []

    def add_route(
        self,
        condition: Callable[[PlatformEvent], bool],
        handler: Callable[[PlatformEvent], None],
    ) -> None:
        """Register a routing rule with filter condition."""
        self._rules.append((condition, handler))

    def route(self, event: PlatformEvent) -> int:
        """Route event through matching rules."""
        matched = 0
        for cond, handler in self._rules:
            if cond(event):
                try:
                    handler(event)
                    matched += 1
                except Exception as exc:
                    logger.error("PlatformEventRouter route handler error: %s", exc)
        return matched
