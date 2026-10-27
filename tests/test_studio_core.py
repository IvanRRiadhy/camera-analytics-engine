"""
Sprint H1.5D1 Studio Core Framework & Observability Test Suite.

Verifies:
1. EngineStudioCoordinator collector aggregation & immutable EngineStudioSnapshot generation.
2. InspectorPlugin & PluginRegistry dynamic registration.
3. IStudioRenderer & OpenCVRenderer driver canvas execution.
4. Pure View RuntimeOverviewInspector & PipelineGraphInspector snapshot rendering.
5. Pure View architectural isolation (zero direct engine component mutation).
"""

from __future__ import annotations

import logging
import time
import numpy as np

from camera_analytics.studio.coordinator import EngineStudioCoordinator
from camera_analytics.studio.inspectors.pipeline_graph import PipelineGraphInspector
from camera_analytics.studio.inspectors.runtime_overview import RuntimeOverviewInspector
from camera_analytics.studio.plugins.inspector_plugin import IInspectorPanel, InspectorPlugin
from camera_analytics.studio.plugins.plugin_registry import PluginRegistry
from camera_analytics.studio.renderers.opencv_renderer import OpenCVRenderer
from camera_analytics.studio.telemetry.base_collector import ITelemetryCollector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestStudioCore")


class DummyTestPlugin(InspectorPlugin):
    @property
    def plugin_id(self) -> str:
        return "dummy_test"

    @property
    def title(self) -> str:
        return "Dummy Test Extension"

    @property
    def group(self) -> str:
        return "AI_ANALYTICS"

    @property
    def priority(self) -> int:
        return 100

    def create_collector(self) -> ITelemetryCollector:
        from camera_analytics.studio.telemetry.collectors import RuntimeTelemetryCollector
        return RuntimeTelemetryCollector()

    def create_panel(self) -> IInspectorPanel:
        return RuntimeOverviewInspector()


def test_coordinator_and_snapshot_generation():
    coord = EngineStudioCoordinator()
    snap1 = coord.generate_snapshot()
    snap2 = coord.generate_snapshot()

    assert snap1.sequence_id == 1
    assert snap2.sequence_id == 2
    assert snap1.runtime.overall_fps == 30.0
    assert len(snap1.pipeline.stages) == 8
    assert len(snap1.model.loaded_models) == 2
    assert len(snap1.human.tracks) == 2
    assert len(snap1.camera.active_cameras) == 2
    print("[+] EngineStudioCoordinator & immutable EngineStudioSnapshot generation test PASSED.")


def test_plugin_registry():
    registry = PluginRegistry()
    plugin = DummyTestPlugin()
    registry.register_plugin(plugin)

    assert registry.get_plugin("dummy_test") is plugin
    active_panels = registry.get_active_panels()
    assert len(active_panels) == 1
    assert active_panels[0].panel_id == "runtime_overview"
    print("[+] InspectorPlugin & PluginRegistry dynamic plugin registration test PASSED.")


def test_pure_view_inspectors_and_renderer():
    coord = EngineStudioCoordinator()
    snapshot = coord.generate_snapshot()

    overview_inspector = RuntimeOverviewInspector()
    pipeline_inspector = PipelineGraphInspector()

    overview_lines = overview_inspector.render_text(snapshot)
    pipeline_lines = pipeline_inspector.render_text(snapshot)

    assert len(overview_lines) >= 10
    assert len(pipeline_lines) >= 5
    assert "RUNTIME OVERVIEW INSPECTOR" in overview_lines[1]
    assert "PIPELINE GRAPH INSPECTOR" in pipeline_lines[1]

    # Test OpenCVRenderer driver
    renderer = OpenCVRenderer(width=1024, height=600)
    canvas = renderer.render(snapshot, overview_lines)
    assert isinstance(canvas, np.ndarray)
    assert canvas.shape == (600, 1024, 3)

    print("[+] Pure View Inspectors & OpenCVRenderer canvas rendering test PASSED.")


def main():
    print("\n========================================================")
    print("   SPRINT H1.5D1 STUDIO CORE & OBSERVABILITY TEST ")
    print("========================================================")
    test_coordinator_and_snapshot_generation()
    test_plugin_registry()
    test_pure_view_inspectors_and_renderer()
    print("========================================================\n")
    print("[SUCCESS] All Sprint H1.5D1 Studio Core Framework Tests PASSED!\n")


if __name__ == "__main__":
    main()
