"""
Event Timeline Pure View Inspector (Sprint H1.5D1.6).

100% Pure View panel reading EngineStudioSnapshot and rendering Chronological Event Timeline UI lines
without touching engine internal states directly.
"""

from __future__ import annotations

from camera_analytics.studio.plugins.inspector_plugin import IInspectorPanel
from camera_analytics.studio.snapshot.engine_studio_snapshot import EngineStudioSnapshot


class EventTimelineInspector(IInspectorPanel):
    """Pure View Inspector for Chronological Event Timeline metrics."""

    @property
    def panel_id(self) -> str:
        return "event_timeline"

    @property
    def title(self) -> str:
        return "Event Timeline"

    def render_text(self, snapshot: EngineStudioSnapshot) -> list[str]:
        """Render text lines from EngineStudioSnapshot."""
        ev = snapshot.event_timeline
        lines = [
            "==================================================================================",
            "                              13. EVENT TIMELINE                                  ",
            "==================================================================================",
            " TIME     EVENT TYPE         TRACK ID  MESSAGE",
            "----------------------------------------------------------------------------------",
        ]
        for e in ev.recent_events:
            lines.append(f" {e.timestamp_formatted:<8} {e.event_type:<18} Track #{e.track_id:<3} {e.message}")
        lines.append("==================================================================================")
        return lines
