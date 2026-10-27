"""
Runtime Overview Pure View Inspector (Sprint H1.5D1).

100% Pure View panel reading EngineStudioSnapshot and rendering Runtime Overview UI lines
without touching engine internal states directly.
"""

from __future__ import annotations

from camera_analytics.studio.plugins.inspector_plugin import IInspectorPanel
from camera_analytics.studio.snapshot.engine_studio_snapshot import EngineStudioSnapshot


class RuntimeOverviewInspector(IInspectorPanel):
    """Pure View Inspector for Runtime Overview metrics."""

    @property
    def panel_id(self) -> str:
        return "runtime_overview"

    @property
    def title(self) -> str:
        return "Runtime Overview"

    def render_text(self, snapshot: EngineStudioSnapshot) -> list[str]:
        """Render text lines from EngineStudioSnapshot."""
        r = snapshot.runtime
        lines = [
            "==================================================================================",
            "                            1. RUNTIME OVERVIEW INSPECTOR                         ",
            "==================================================================================",
            f" ENGINE STATUS: RUNNING | MODE: STANDALONE | DEVICE: {r.gpu_device_name}",
            "----------------------------------------------------------------------------------",
            " SYSTEM METRICS",
            f"  Overall FPS      : {r.overall_fps:.1f} FPS         Frame Time      : {r.frame_time_ms:.2f} ms",
            f"  Pipeline Latency : {r.pipeline_latency_ms:.2f} ms        CPU Util        : {r.cpu_utilization_pct:.1f} %",
            f"  RAM Usage        : {r.ram_usage_mb:.1f} MB        GPU VRAM Usage  : {r.gpu_memory_vram_mb:.1f} MB",
            f"  GPU Compute Util : {r.gpu_compute_utilization_pct:.1f} %",
            "",
            " QUEUE HEALTH & DROPPED FRAMES",
            f"  Frame Queue      : {r.frame_queue_size} / {r.frame_queue_capacity} (Dropped: {r.dropped_frames_count})",
            f"  Inference Queue  : {r.inference_queue_size} / 30",
            f"  Snapshot Queue   : {r.snapshot_queue_size} / 50",
            f"  Comm. Queue      : {r.communication_queue_size} / 100",
            "==================================================================================",
        ]
        return lines
