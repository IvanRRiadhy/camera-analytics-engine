"""
InspectorPlugin Extension Interface (Sprint H1.5D1.5).

Defines the universal plugin architecture interface with manifest metadata validation.
Allows future capabilities (Emotion, PPE, Vehicle Analytics, OCR, Face Recognition, Gesture)
to plug into the Studio without modifying core Studio source code.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from camera_analytics.studio.snapshot.engine_studio_snapshot import EngineStudioSnapshot
from camera_analytics.studio.telemetry.base_collector import ITelemetryCollector


class IInspectorPanel(ABC):
    """Abstract interface for Pure View Inspector panels."""

    @property
    @abstractmethod
    def panel_id(self) -> str:
        """Unique inspector panel identifier."""
        pass

    @property
    @abstractmethod
    def title(self) -> str:
        """Display title for Studio tab bar."""
        pass

    @abstractmethod
    def render_text(self, snapshot: EngineStudioSnapshot) -> list[str]:
        """Render inspector UI text content from EngineStudioSnapshot without touching engine state."""
        pass


class InspectorPlugin(ABC):
    """Universal plugin interface with manifest metadata for Studio Inspector Extensions."""

    @property
    @abstractmethod
    def plugin_id(self) -> str:
        """Unique plugin identifier (e.g. 'emotion_inspector')."""
        pass

    @property
    @abstractmethod
    def title(self) -> str:
        """Display title for Studio tab bar."""
        pass

    @property
    def version(self) -> str:
        """Plugin semver version."""
        return "1.0.0"

    @property
    def author(self) -> str:
        """Plugin author/team."""
        return "CCTV Analytics Team"

    @property
    def engine_version(self) -> str:
        """Target compatible engine version."""
        return "2.0.0"

    @property
    def dependencies(self) -> tuple[str, ...]:
        """List of required plugin IDs."""
        return ()

    @property
    def description(self) -> str:
        """Brief plugin description."""
        return "Studio Inspector Extension"

    @property
    @abstractmethod
    def group(self) -> str:
        """Inspector group ('AI_ANALYTICS', 'SYSTEM', 'DIAGNOSTICS')."""
        pass

    @property
    @abstractmethod
    def priority(self) -> int:
        """Tab bar ordering priority."""
        pass

    @abstractmethod
    def create_collector(self) -> ITelemetryCollector:
        """Instantiate target telemetry collector."""
        pass

    @abstractmethod
    def create_panel(self) -> IInspectorPanel:
        """Instantiate Pure View inspector panel."""
        pass
