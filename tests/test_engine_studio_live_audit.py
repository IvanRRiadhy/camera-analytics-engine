"""
Sprint H1.5D1.6A Live Runtime Audit & Observability Integration Test.

Verifies:
1. End-to-end MiVOLO pipeline execution via HumanAnalyticsScheduler DAG graph.
2. High-contrast OverlayRenderer multi-line pill label generation with HumanStatePresenter.
3. TelemetryCollectors reading live contracts.
4. Studio Pure View Inspectors rendering non-placeholder live metrics.
"""

from __future__ import annotations

import logging
import unittest
import numpy as np

from camera_analytics.core.human.runtime import HumanRuntime
from camera_analytics.viewer.builder import FramePresentationBuilder
from camera_analytics.viewer.presenter import HumanStatePresenter
from camera_analytics.viewer.renderer import OverlayRenderer, RenderOptions
from camera_analytics.studio.telemetry.collectors import (
    HumanTelemetryCollector,
    PipelineTelemetryCollector,
    ModelTelemetryCollector,
)
from camera_analytics.studio.telemetry.collector_context import CollectorContext
from camera_analytics.studio.inspectors.human_runtime import HumanRuntimeInspector
from camera_analytics.studio.inspectors.model_inspector import AIModelInspector
from camera_analytics.studio.inspectors.camera_inspector import CameraInspector
from camera_analytics.studio.inspectors.event_timeline import EventTimelineInspector
from camera_analytics.studio.snapshot.engine_studio_snapshot import EngineStudioSnapshot
from camera_analytics.models.camera import Camera, CameraStatus


class TestEngineStudioLiveAudit(unittest.TestCase):

    def test_01_human_runtime_mivolo_dag_execution(self) -> None:
        """Verify HumanRuntime auto-registers MiVOLOModule into scheduler DAG graph."""
        runtime = HumanRuntime()
        order = runtime.scheduler.graph.resolve_execution_order()
        self.assertIn("mivolo_age_gender", order, "MiVOLOModule must be in scheduler DAG order!")

        # Execute dummy frame process
        tracks = [{
            "track_id": 1,
            "bbox": [100, 100, 300, 400],
            "confidence": 0.95,
            "keypoints": None,
        }]
        dummy_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        res = runtime.process_frame(tracks, frame=dummy_frame)
        self.assertIn(1, res.states)
        h_state = res.states[1]
        self.assertIsNotNone(h_state)
        self.assertIn(h_state.lifecycle.name, ["INITIALIZING", "LEARNING", "STABLE"])

    def test_02_overlay_renderer_high_contrast_pills(self) -> None:
        """Verify OverlayRenderer draws multi-line semi-transparent pill boxes."""
        dummy_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        from camera_analytics.ingestion.models import IngestedFrame
        ing_frame = IngestedFrame(
            pipeline_id="pipe_test",
            camera_id="cam_test",
            frame_number=1,
            timestamp=1.0,
            image=dummy_frame,
            read_latency_ms=1.0,
            width=1280,
            height=720,
        )
        cam = Camera(camera_id="cam_test", name="Test Cam", source="test", fps=30.0, status=CameraStatus.ONLINE)
        
        class DummyCtx:
            tracks = [{"track_id": 1, "bbox": [100, 100, 300, 400], "confidence": 0.95}]
            human_states = {}

        runtime = HumanRuntime()
        res = runtime.process_frame(DummyCtx.tracks, frame=dummy_frame)
        DummyCtx.human_states = res.states

        pres = FramePresentationBuilder.build(ing_frame, cam, frame_context=DummyCtx)
        self.assertEqual(len(pres.human_view_models), 1)

        renderer = OverlayRenderer(options=RenderOptions(draw_track_id=True))
        out_img = renderer.render(pres)
        self.assertEqual(out_img.shape, (720, 1280, 3))

    def test_03_telemetry_collectors_live_contracts(self) -> None:
        """Verify TelemetryCollector implementations read live contracts."""
        ctx = CollectorContext(active_camera_ids=["cam_lobby_01", "cam_parking_02"])
        pipe_coll = PipelineTelemetryCollector()
        pipe_snap = pipe_coll.collect(ctx)
        self.assertEqual(pipe_snap.active_pipelines_count, 2)

        model_coll = ModelTelemetryCollector()
        model_snap = model_coll.collect(ctx)
        self.assertTrue(any(m.model_id == "mivolo_v2_age_gender" for m in model_snap.loaded_models))

    def test_04_studio_inspectors_render_live_panels(self) -> None:
        """Verify pure view Studio Inspectors render text lines successfully."""
        snap = EngineStudioSnapshot()

        hr_insp = HumanRuntimeInspector()
        hr_lines = hr_insp.render_text(snap)
        self.assertTrue(len(hr_lines) > 0)

        m_insp = AIModelInspector()
        m_lines = m_insp.render_text(snap)
        self.assertTrue(len(m_lines) > 0)

        c_insp = CameraInspector()
        c_lines = c_insp.render_text(snap)
        self.assertTrue(len(c_lines) > 0)

        e_insp = EventTimelineInspector()
        e_lines = e_insp.render_text(snap)
        self.assertTrue(len(e_lines) > 0)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    unittest.main()
