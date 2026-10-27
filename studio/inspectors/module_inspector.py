"""
Module Inspector Pure View Panel (Sprint H1.5D1.6C).

100% Pure View panel reading EngineStudioSnapshot and rendering Module telemetry lines.
"""

from __future__ import annotations

from camera_analytics.studio.plugins.inspector_plugin import IInspectorPanel
from camera_analytics.studio.snapshot.engine_studio_snapshot import EngineStudioSnapshot


class ModuleInspector(IInspectorPanel):
    """Pure View Inspector for Subsystem Module operational metrics."""

    @property
    def panel_id(self) -> str:
        return "module"

    @property
    def title(self) -> str:
        return "Module Inspector"

    def render_text(self, snapshot: EngineStudioSnapshot) -> list[str]:
        """Render text lines from EngineStudioSnapshot."""
        m = snapshot.module
        lines = [
            "==================================================================================",
            "                       5. SUBSYSTEM MODULE INSPECTOR                              ",
            "==================================================================================",
            f" ACTIVE MODULES: {len(m.active_modules)}",
            "----------------------------------------------------------------------------------",
            " MODULE ID           PRIORITY  STRIDE  EXEC COUNT  SKIPPED CNT  STATUS",
            "----------------------------------------------------------------------------------",
        ]
        for mod in m.active_modules:
            is_en = getattr(mod, "enabled", getattr(mod, "is_active", True))
            st = "ACTIVE" if is_en else "DISABLED"
            lines.append(
                f" {mod.module_id:<20} {mod.priority:<9} {mod.frame_stride:<7} {mod.execution_count:<11} {mod.skipped_count:<12} {st}"
            )
        lines.append("==================================================================================")
        return lines
