"""
Abstract IStudioRenderer Interface (Sprint H1.5D1).

Framework-agnostic rendering interface decoupling Studio rendering from specific GUI drivers
(OpenCVRenderer, PySideRenderer, DearImGuiRenderer, WebRenderer).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from camera_analytics.studio.snapshot.engine_studio_snapshot import EngineStudioSnapshot


class IStudioRenderer(ABC):
    """Abstract driver interface for rendering Engine Studio UI snapshots."""

    @property
    @abstractmethod
    def driver_id(self) -> str:
        """Unique driver identifier (e.g. 'opencv', 'pyside', 'imgui', 'web')."""
        pass

    @abstractmethod
    def render(self, snapshot: EngineStudioSnapshot, panel_id: str = "runtime_overview") -> Any:
        """Render snapshot onto target display canvas."""
        pass
