"""
Camera Pure View Inspector (Sprint H1.5D1.6).

100% Pure View panel reading EngineStudioSnapshot and rendering Camera Stream Inspector UI lines
without touching engine internal states directly.
"""

from __future__ import annotations

from camera_analytics.studio.plugins.inspector_plugin import IInspectorPanel
from camera_analytics.studio.snapshot.engine_studio_snapshot import EngineStudioSnapshot


class CameraInspector(IInspectorPanel):
    """Pure View Inspector for Camera Stream metrics."""

    @property
    def panel_id(self) -> str:
        return "camera_inspector"

    @property
    def title(self) -> str:
        return "Camera Inspector"

    def render_text(self, snapshot: EngineStudioSnapshot) -> list[str]:
        """Render text lines from EngineStudioSnapshot."""
        c = snapshot.camera
        lines = [
            "==================================================================================",
            "                                12. CAMERA INSPECTOR                              ",
            "==================================================================================",
            f" ACTIVE CAMERA PIPELINES: {len(c.active_cameras)}",
            "----------------------------------------------------------------------------------",
            " CAMERA ID       STATUS     RESOLUTION  FPS    BITRATE    LATENCY  DROPPED  RECONNECTS",
            "----------------------------------------------------------------------------------",
        ]
        for cam in c.active_cameras:
            lines.append(
                f" {cam.camera_id:<15} {cam.status:<10} {cam.resolution:<11} {cam.fps:>4.1f}  {cam.bitrate_kbps:>6.0f} kbps {cam.latency_ms:>5.1f} ms {cam.dropped_frames_count:<8} {cam.reconnect_count}"
            )
        lines.append("==================================================================================")
        return lines
