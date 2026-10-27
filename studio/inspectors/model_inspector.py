"""
AI Model Pure View Inspector (Sprint H1.5D1.6).

100% Pure View panel reading EngineStudioSnapshot and rendering AI Model Inspector UI lines
without touching engine internal states directly.
"""

from __future__ import annotations

from camera_analytics.studio.plugins.inspector_plugin import IInspectorPanel
from camera_analytics.studio.snapshot.engine_studio_snapshot import EngineStudioSnapshot


class AIModelInspector(IInspectorPanel):
    """Pure View Inspector for AI Model metrics."""

    @property
    def panel_id(self) -> str:
        return "model_inspector"

    @property
    def title(self) -> str:
        return "AI Model Inspector"

    def render_text(self, snapshot: EngineStudioSnapshot) -> list[str]:
        """Render text lines from EngineStudioSnapshot."""
        m = snapshot.model
        lines = [
            "==================================================================================",
            "                                3. AI MODEL INSPECTOR                             ",
            "==================================================================================",
            " MODEL ID        STATUS   BACKEND      DEVICE   FP16  VRAM (MB)  LATENCY (AVG/P95) BATCH EXECUTIONS",
            "----------------------------------------------------------------------------------",
        ]
        for entry in m.loaded_models:
            fp16_str = "YES" if entry.is_fp16 else "NO"
            lines.append(
                f" {entry.model_id:<15} {entry.status:<8} {entry.backend:<12} {entry.device:<8} {fp16_str:<5} {entry.vram_mb:>7.1f} MB  {entry.avg_latency_ms:>5.2f} ms / {entry.p95_latency_ms:>5.1f} ms {entry.batch_size:<5} {entry.success_count:,}"
            )
        lines.append("==================================================================================")
        return lines
