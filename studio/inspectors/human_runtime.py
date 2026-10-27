"""
Human Runtime Track Explorer Pure View Inspector (Sprint H1.5D1.6).

100% Pure View panel reading EngineStudioSnapshot and rendering Live Track Explorer UI lines
without touching engine internal states directly.
"""

from __future__ import annotations

from camera_analytics.studio.plugins.inspector_plugin import IInspectorPanel
from camera_analytics.studio.snapshot.engine_studio_snapshot import EngineStudioSnapshot


class HumanRuntimeInspector(IInspectorPanel):
    """Pure View Inspector for Live Track Explorer & Human State metrics."""

    @property
    def panel_id(self) -> str:
        return "human_runtime"

    @property
    def title(self) -> str:
        return "Human Runtime (Track Explorer)"

    def render_text(self, snapshot: EngineStudioSnapshot) -> list[str]:
        """Render text lines from EngineStudioSnapshot."""
        h = snapshot.human
        lines = [
            "==================================================================================",
            "                   4. HUMAN RUNTIME INSPECTOR (TRACK EXPLORER)                   ",
            "==================================================================================",
            f" ACTIVE PERSON TRACKS: {h.active_tracks_count}",
            "----------------------------------------------------------------------------------",
            " TRACK ID  LIFECYCLE  AGE (EMA)   GENDER (CONF)  QUALITY  ZONE            LIFETIME  INFERENCE CNT",
            "----------------------------------------------------------------------------------",
        ]
        for trk in h.tracks:
            lines.append(
                f" Track #{trk.track_id:<3} {trk.lifecycle:<10} {trk.age:.1f} ({trk.ema_age:.1f})  {trk.gender:<6} ({trk.confidence:.2f})  {trk.quality_score:.2f}     {trk.zone:<15} {trk.lifetime_s:>5.1f}s    {trk.inference_count}"
            )
        lines.append("==================================================================================")
        return lines
