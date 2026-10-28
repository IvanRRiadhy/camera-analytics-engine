import unittest
import numpy as np
from unittest.mock import MagicMock

from camera_analytics.context.unified_context import SharedAnalyticsContext
from camera_analytics.models.camera import Camera
from camera_analytics.plugins.framework.states import PluginState
from camera_analytics.plugins.vehicle_lpr.plugin import VehicleLPRPlugin
from camera_analytics.plugins.vehicle_lpr.tracker import PlateTrack
from camera_analytics.viewer.builder import FramePresentationBuilder
from camera_analytics.viewer.models import FramePresentation, PresentedPlateBox
from camera_analytics.viewer.renderer import OverlayRenderer, RenderOptions
from camera_analytics.ingestion.models import IngestedFrame


class TestVehicleLPROverlay(unittest.TestCase):
    def test_lpr_plugin_exports_overlay_metadata(self):
        plugin = VehicleLPRPlugin()
        plugin.state = PluginState.RUNNING

        # Add mock plate track
        track = PlateTrack(track_id=1, bbox=(50.0, 60.0, 200.0, 110.0), conf=0.92, frame_idx=0)
        plugin.tracker.tracks[1] = track

        # Add mock voting engine with observation
        mock_voting_engine = MagicMock()
        mock_voting_res = MagicMock(
            plate_text="B1234ABC",
            status="GRAMMAR_VALID",
            winner_share=0.85,
            total_votes=5,
            best_reading={"mean_box_conf_all": 0.94},
        )
        mock_voting_engine.compute_consensus.return_value = mock_voting_res
        plugin._voting_engines[1] = mock_voting_engine

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        ctx = SharedAnalyticsContext(frame=frame, frame_index=0, camera_id="cam_test", pipeline_id="pipe_test")

        # Mock tracker update so it doesn't try to run inference
        plugin.tracker.update = MagicMock(return_value=([(track, True)], []))
        plugin.localizer.localize = MagicMock(return_value=[])

        plugin.process(ctx)

        self.assertIn("lpr_plates", ctx.metadata)
        plates = ctx.metadata["lpr_plates"]
        self.assertEqual(len(plates), 1)
        self.assertEqual(plates[0]["track_id"], 1)
        self.assertEqual(plates[0]["bbox"], [50.0, 60.0, 200.0, 110.0])
        self.assertEqual(plates[0]["plate_text"], "B1234ABC")
        self.assertEqual(plates[0]["confidence"], 0.94)
        self.assertEqual(plates[0]["detector_confidence"], 0.92)
        self.assertTrue(plates[0]["is_consensus"])

    def test_frame_presentation_builder_plate_boxes(self):
        camera = Camera(camera_id="cam_test", name="Test Camera", source="test", width=640, height=480, fps=30.0)
        ingested_frame = IngestedFrame(
            pipeline_id="pipe_test",
            camera_id="cam_test",
            frame_number=1,
            timestamp=100.0,
            read_latency_ms=5.0,
            image=np.zeros((480, 640, 3), dtype=np.uint8),
            width=640,
            height=480,
        )

        ctx = SharedAnalyticsContext(
            frame=ingested_frame.image,
            frame_index=1,
            camera_id="cam_test",
            metadata={
                "lpr_plates": [
                    {
                        "track_id": 42,
                        "bbox": [100.0, 150.0, 250.0, 200.0],
                        "detector_confidence": 0.90,
                        "plate_text": "D5678XYZ",
                        "confidence": 0.88,
                        "is_consensus": True,
                    }
                ]
            },
        )

        pres = FramePresentationBuilder.build(frame=ingested_frame, camera=camera, frame_context=ctx)
        self.assertEqual(len(pres.plate_boxes), 1)
        pb = pres.plate_boxes[0]
        self.assertIsInstance(pb, PresentedPlateBox)
        self.assertEqual(pb.track_id, 42)
        self.assertEqual(pb.x1, 100)
        self.assertEqual(pb.y1, 150)
        self.assertEqual(pb.x2, 250)
        self.assertEqual(pb.y2, 200)
        self.assertEqual(pb.plate_text, "D5678XYZ")
        self.assertEqual(pb.confidence, 0.88)
        self.assertEqual(pb.detector_confidence, 0.90)
        self.assertTrue(pb.is_consensus)

    def test_overlay_renderer_renders_plate_box_and_text(self):
        camera = Camera(camera_id="cam_test", name="Test Camera", source="test", width=640, height=480, fps=30.0)
        image = np.zeros((480, 640, 3), dtype=np.uint8)

        pb = PresentedPlateBox(
            track_id=7,
            x1=100,
            y1=120,
            x2=280,
            y2=170,
            plate_text="B1234ABC",
            confidence=0.95,
            detector_confidence=0.91,
            is_consensus=True,
        )

        pres = FramePresentation(
            camera_id="cam_test",
            camera_name="Test Camera",
            frame_number=1,
            timestamp=100.0,
            image=image,
            plate_boxes=(pb,),
        )

        renderer = OverlayRenderer(options=RenderOptions(draw_plates=True))
        canvas = renderer.render(pres)

        # Ensure the canvas was drawn on (pixels changed from 0)
        self.assertGreater(np.sum(canvas), 0)

        # Disable draw_plates and ensure plate is not drawn
        renderer_no_plate = OverlayRenderer(options=RenderOptions(draw_plates=False))
        canvas_clean = renderer_no_plate.render(pres)
        self.assertEqual(np.sum(canvas_clean), 0)


if __name__ == "__main__":
    unittest.main()
