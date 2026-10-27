"""
Pipeline Graph Pure View Inspector (Sprint H1.5D1).

100% Pure View panel reading EngineStudioSnapshot and rendering Pipeline Graph DAG UI lines
without touching engine internal states directly.
"""

from __future__ import annotations

from camera_analytics.studio.plugins.inspector_plugin import IInspectorPanel
from camera_analytics.studio.snapshot.engine_studio_snapshot import EngineStudioSnapshot


class PipelineGraphInspector(IInspectorPanel):
    """Pure View Inspector for Pipeline Graph DAG metrics."""

    @property
    def panel_id(self) -> str:
        return "pipeline_graph"

    @property
    def title(self) -> str:
        return "Pipeline Graph"

    def render_text(self, snapshot: EngineStudioSnapshot) -> list[str]:
        """Render text lines from EngineStudioSnapshot."""
        p = snapshot.pipeline
        lines = [
            "==================================================================================",
            "                            2. PIPELINE GRAPH INSPECTOR                           ",
            "==================================================================================",
            f" ACTIVE PIPELINES: {p.active_pipelines_count} | DAG STAGES: {len(p.stages)}",
            "----------------------------------------------------------------------------------",
        ]
        for st in p.stages:
            lines.append(
                f"  [{st.stage_name:<16}] -> Lat: {st.latency_ms:>5.2f} ms (Avg: {st.avg_latency_ms:>5.2f} ms) | Queue: {st.queue_size} | Drops: {st.dropped_count} | Status: {st.status}"
            )
        lines.append("==================================================================================")
        return lines
