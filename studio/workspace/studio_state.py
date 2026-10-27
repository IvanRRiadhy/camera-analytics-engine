"""
StudioState Workspace UI State Container (Sprint H1.5D1.5).

Manages mutable UI selection states (selected tab, selected camera, selected track, search filters)
without mixing mutable presentation state with immutable telemetry snapshots.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class StudioState:
    """Mutable UI workspace state container."""

    selected_tab: str = "runtime_overview"
    selected_camera: str = "cam_lobby_01"
    selected_track_id: Optional[int] = None
    selected_workspace: str = "default"
    search_text: str = ""
    active_filters: dict[str, Any] = field(default_factory=dict)
    panel_visibility: dict[str, bool] = field(default_factory=dict)
    fullscreen: bool = False
    window_layout: str = "tabs"
