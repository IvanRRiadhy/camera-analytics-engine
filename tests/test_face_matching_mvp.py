"""Unit tests for Face Matching plugin MVP (synthetic only, no real models/faces)."""

import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock

import numpy as np

from camera_analytics.context.unified_context import SharedAnalyticsContext
from camera_analytics.models.camera import Camera
from camera_analytics.ingestion.models import IngestedFrame
from camera_analytics.plugins.face_matching.config import FaceMatchConfig
from camera_analytics.plugins.face_matching.consensus import (
    ConsensusBuffer,
    FaceObservation,
    PersonCooldownManager,
)
from camera_analytics.plugins.face_matching.detector import FaceDetection
from camera_analytics.plugins.face_matching.gallery import (
    FaceGallery,
    PersonCandidate,
    PersonMetadata,
)
from camera_analytics.plugins.face_matching.plugin import FaceMatchingPlugin
from camera_analytics.viewer.builder import FramePresentationBuilder
from camera_analytics.viewer.models import FramePresentation, PresentedFaceBox
from camera_analytics.viewer.renderer import OverlayRenderer, RenderOptions


class FakeFaceDetector:
    """Synthetic face detector for testing."""

    def __init__(self, detections=None):
        self.detections = detections if detections is not None else []

    def detect(self, frame_bgr):
        return list(self.detections)


class FakeFaceEmbedder:
    """Synthetic face embedder for testing."""

    def __init__(self, embedding_dim=128, constant_vector=None):
        self.dim = embedding_dim
        if constant_vector is not None:
            self.vec = (constant_vector / np.linalg.norm(constant_vector)).astype(np.float32)
        else:
            v = np.ones(self.dim, dtype=np.float32)
            self.vec = (v / np.linalg.norm(v)).astype(np.float32)

    def embed(self, frame: np.ndarray, face) -> np.ndarray:
        return self.vec.copy()

    def align(self, frame: np.ndarray, face) -> np.ndarray:
        return np.zeros((112, 112, 3), dtype=np.uint8)

    def embed_aligned(self, aligned_face: np.ndarray) -> np.ndarray:
        return self.vec.copy()


class TestFaceGallery(unittest.TestCase):
    """Gallery unit tests: enrollment validation, caching, person-level matching."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.cache_dir = os.path.join(self.test_dir, "cache")
        os.makedirs(self.cache_dir, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _create_person_files(self, person_id, count=1):
        import cv2
        for i in range(count):
            img = np.full((120, 120, 3), fill_value=128, dtype=np.uint8)
            suffix = f"_{i}" if count > 1 else ""
            img_path = os.path.join(self.test_dir, f"{person_id}{suffix}.jpg")
            cv2.imwrite(img_path, img)

        meta_path = os.path.join(self.test_dir, f"{person_id}_meta.json")
        import json
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump({"name": f"Test {person_id}", "department": "QA"}, f)

    def test_gallery_enrollment_rejects_zero_faces(self):
        self._create_person_files("P0001", count=1)
        detector = FakeFaceDetector(detections=[])  # 0 faces
        embedder = FakeFaceEmbedder()

        gallery = FaceGallery.load(self.test_dir, detector, embedder, cache_dir=self.cache_dir)
        self.assertEqual(gallery.total_people, 0)
        self.assertEqual(gallery.rejected_images_count, 1)

    def test_gallery_enrollment_rejects_multiple_faces(self):
        self._create_person_files("P0001", count=1)
        d1 = FaceDetection((10, 10, 80, 80), [(20, 20), (40, 20), (30, 30), (25, 45), (35, 45)], 0.95)
        d2 = FaceDetection((50, 50, 80, 80), [(60, 60), (80, 60), (70, 70), (65, 85), (75, 85)], 0.90)
        detector = FakeFaceDetector(detections=[d1, d2])  # 2 faces
        embedder = FakeFaceEmbedder()

        gallery = FaceGallery.load(self.test_dir, detector, embedder, cache_dir=self.cache_dir)
        self.assertEqual(gallery.total_people, 0)
        self.assertEqual(gallery.rejected_images_count, 1)

    def test_gallery_enrollment_rejects_tiny_face(self):
        self._create_person_files("P0001", count=1)
        # width = 50 < 80px min requirement
        d = FaceDetection((10, 10, 50, 50), [(20, 20), (40, 20), (30, 30), (25, 45), (35, 45)], 0.95)
        detector = FakeFaceDetector(detections=[d])
        embedder = FakeFaceEmbedder()

        gallery = FaceGallery.load(self.test_dir, detector, embedder, cache_dir=self.cache_dir)
        self.assertEqual(gallery.total_people, 0)
        self.assertEqual(gallery.rejected_images_count, 1)

    def test_gallery_single_image_person_warns(self):
        self._create_person_files("P0001", count=1)
        d = FaceDetection((10, 10, 90, 90), [(25, 30), (65, 30), (45, 50), (30, 70), (60, 70)], 0.95)
        detector = FakeFaceDetector(detections=[d])
        embedder = FakeFaceEmbedder()

        with self.assertLogs("camera_analytics.plugins.face_matching.gallery", level="WARNING") as cm:
            gallery = FaceGallery.load(self.test_dir, detector, embedder, cache_dir=self.cache_dir)
            self.assertEqual(gallery.total_people, 1)
            self.assertTrue(any("single enrolled image" in msg or "only 1 enrolled image" in msg for msg in cm.output))

    def test_gallery_cache_hit_on_second_load(self):
        self._create_person_files("P0001", count=1)
        d = FaceDetection((10, 10, 90, 90), [(25, 30), (65, 30), (45, 50), (30, 70), (60, 70)], 0.95)
        detector = MagicMock()
        detector.detect.return_value = [d]
        embedder = MagicMock()
        v = np.ones(128, dtype=np.float32)
        embedder.embed.return_value = v / np.linalg.norm(v)

        # First load: computes and writes cache
        g1 = FaceGallery.load(self.test_dir, detector, embedder, cache_dir=self.cache_dir)
        self.assertEqual(g1.total_people, 1)
        self.assertEqual(detector.detect.call_count, 1)
        self.assertEqual(embedder.embed.call_count, 1)

        # Second load: hits disk cache without calling detect or embed
        detector.reset_mock()
        embedder.reset_mock()
        g2 = FaceGallery.load(self.test_dir, detector, embedder, cache_dir=self.cache_dir)
        self.assertEqual(g2.total_people, 1)
        self.assertEqual(detector.detect.call_count, 0)
        self.assertEqual(embedder.embed.call_count, 0)

    def test_gallery_person_level_top2_ignores_same_person(self):
        # Person A has 2 embeddings (v1 and slightly rotated v2)
        v1 = np.zeros(128, dtype=np.float32)
        v1[0] = 1.0
        v2 = np.zeros(128, dtype=np.float32)
        v2[0] = 0.95
        v2[1] = 0.312
        v2 = v2 / np.linalg.norm(v2)

        # Person B has 1 embedding
        v3 = np.zeros(128, dtype=np.float32)
        v3[0] = 0.80
        v3[2] = 0.60
        v3 = v3 / np.linalg.norm(v3)

        embs = np.stack([v1, v2, v3], axis=0)
        owners = ["P0001", "P0001", "P0002"]
        persons = {
            "P0001": PersonMetadata(person_id="P0001", full_name="Alice"),
            "P0002": PersonMetadata(person_id="P0002", full_name="Bob"),
        }

        gallery = FaceGallery(embeddings=embs, owner_ids=owners, persons=persons)

        # Query vector is v1
        query = np.zeros(128, dtype=np.float32)
        query[0] = 1.0

        matches = gallery.match(query, top_k=2)
        self.assertEqual(len(matches), 2)
        # Top-1 is Alice, Top-2 MUST be Bob (not Alice's second image!)
        self.assertEqual(matches[0].person_id, "P0001")
        self.assertEqual(matches[1].person_id, "P0002")


class TestConsensusBuffer(unittest.TestCase):
    """Consensus logic: window, frame threshold, margin gate, cooldown, no bypass."""

    def test_consensus_needs_n_same_person_observations(self):
        buf = ConsensusBuffer(window_size=15)
        # 2 observations when min_frames=3 -> None
        buf.add_observation(FaceObservation(person_id="P0001", score=0.85, margin=0.10, timestamp_s=1.0, frame_idx=1))
        buf.add_observation(FaceObservation(person_id="P0001", score=0.86, margin=0.10, timestamp_s=1.1, frame_idx=2))
        res = buf.evaluate_consensus(cosine_threshold=0.40, min_margin=0.05, consensus_frames=3)
        self.assertIsNone(res)

        # 3rd observation -> identified
        buf.add_observation(FaceObservation(person_id="P0001", score=0.84, margin=0.12, timestamp_s=1.2, frame_idx=3))
        res = buf.evaluate_consensus(cosine_threshold=0.40, min_margin=0.05, consensus_frames=3)
        self.assertIsNotNone(res)
        self.assertEqual(res.person_id, "P0001")
        self.assertAlmostEqual(res.best_score, 0.86, places=2)

    def test_consensus_margin_gate_blocks_close_second(self):
        buf = ConsensusBuffer(window_size=15)
        # Observations have margin=0.02 which is less than min_margin=0.05
        for i in range(5):
            buf.add_observation(FaceObservation(person_id="P0001", score=0.85, margin=0.02, timestamp_s=float(i), frame_idx=i))
        res = buf.evaluate_consensus(cosine_threshold=0.40, min_margin=0.05, consensus_frames=3)
        self.assertIsNone(res)

    def test_consensus_below_threshold_never_emits(self):
        buf = ConsensusBuffer(window_size=15)
        # Score is 0.35, below cosine_threshold 0.40
        for i in range(5):
            buf.add_observation(FaceObservation(person_id="P0001", score=0.35, margin=0.15, timestamp_s=float(i), frame_idx=i))
        res = buf.evaluate_consensus(cosine_threshold=0.40, min_margin=0.05, consensus_frames=3)
        self.assertIsNone(res)

    def test_consensus_cooldown_suppresses_repeat(self):
        cooldown = PersonCooldownManager(cooldown_s=10.0)
        self.assertTrue(cooldown.is_cooled_down("P0001", current_time_s=100.0))
        cooldown.record_emission("P0001", current_time_s=100.0)
        self.assertFalse(cooldown.is_cooled_down("P0001", current_time_s=105.0))
        self.assertTrue(cooldown.is_cooled_down("P0001", current_time_s=111.0))

    def test_consensus_expired_track_buffers_dropped(self):
        from camera_analytics.plugins.face_matching.tracker import FaceIoUTracker
        tracker = FaceIoUTracker(max_lost_strides=3)
        d1 = FaceDetection((10, 10, 50, 50), [(20, 20), (40, 20), (30, 30), (25, 45), (35, 45)], 0.9)
        active, expired = tracker.update([d1], frame_idx=1)
        self.assertEqual(len(active), 1)
        track_id = active[0].track_id

        # Update tracker with empty detections for 5 frames -> track expires
        all_expired = []
        for f in range(2, 7):
            active, expired = tracker.update([], frame_idx=f)
            all_expired.extend(expired)

        self.assertTrue(any(t.track_id == track_id for t in all_expired))

    def test_consensus_mixed_stream_does_not_emit(self):
        buf = ConsensusBuffer(window_size=6)
        # Stream alternates A, B, A, B, A, B
        for i in range(6):
            pid = "P0001" if i % 2 == 0 else "P0002"
            buf.add_observation(FaceObservation(person_id=pid, score=0.80, margin=0.10, timestamp_s=float(i), frame_idx=i))
        # consensus_frames=4 -> neither has 4
        res = buf.evaluate_consensus(cosine_threshold=0.40, min_margin=0.05, consensus_frames=4)
        self.assertIsNone(res)

    def test_consensus_no_bypass(self):
        """Verify that no code path can mark consensus or emit without meeting ALL gates."""
        buf = ConsensusBuffer(window_size=15)
        # Even with high score 0.99, if margin is below min_margin, consensus MUST be None
        buf.add_observation(FaceObservation(person_id="P0001", score=0.99, margin=0.01, timestamp_s=1.0, frame_idx=1))
        buf.add_observation(FaceObservation(person_id="P0001", score=0.99, margin=0.01, timestamp_s=1.1, frame_idx=2))
        buf.add_observation(FaceObservation(person_id="P0001", score=0.99, margin=0.01, timestamp_s=1.2, frame_idx=3))
        self.assertIsNone(buf.evaluate_consensus(cosine_threshold=0.40, min_margin=0.05, consensus_frames=3))


class TestFaceMatchingPlugin(unittest.TestCase):
    """Plugin integration with synthetic models."""

    def _make_plugin(self, emit_unknown=False):
        from camera_analytics.plugins.face_matching.tracker import FaceIoUTracker
        from camera_analytics.plugins.framework.states import PluginState

        config = FaceMatchConfig(
            frame_stride=1,
            min_face_px=50,
            min_quality=0.20,
            cosine_threshold=0.50,
            min_margin=0.05,
            consensus_frames=3,
            consensus_window=10,
            track_cooldown_s=10.0,
            emit_unknown=emit_unknown,
            overlay_unknown=True,
            debug_scores=True,
        )
        plugin = FaceMatchingPlugin(config=config)

        # Setup gallery with 1 person
        v = np.zeros(128, dtype=np.float32)
        v[0] = 1.0
        embs = np.stack([v], axis=0)
        owners = ["P0001"]
        persons = {
            "P0001": PersonMetadata(person_id="P0001", full_name="Alice Smith", metadata={"dept": "Eng"}),
        }
        gallery = FaceGallery(embeddings=embs, owner_ids=owners, persons=persons)

        plugin.gallery = gallery
        plugin.detector = FakeFaceDetector()
        plugin.embedder = FakeFaceEmbedder(constant_vector=v)
        plugin.tracker = FaceIoUTracker(max_lost_strides=10)
        plugin._cooldown_manager = PersonCooldownManager(cooldown_s=10.0)
        plugin.state = PluginState.RUNNING
        return plugin

    def test_plugin_context_frame_bytes_unchanged(self):
        plugin = self._make_plugin()
        frame = np.full((200, 200, 3), 100, dtype=np.uint8)
        frame_bytes_before = frame.tobytes()

        ctx = SharedAnalyticsContext(frame=frame, frame_index=0, camera_id="cam1", pipeline_id="pipe1")
        plugin.process(ctx)

        self.assertEqual(ctx.frame.tobytes(), frame_bytes_before)

    def test_plugin_width_gate_counted(self):
        plugin = self._make_plugin()
        # Detection with width=30 < min_face_px=50
        plugin.detector.detections = [
            FaceDetection((20, 20, 30, 30), [(25, 25), (35, 25), (30, 30), (27, 40), (33, 40)], 0.9)
        ]
        frame = np.full((200, 200, 3), 100, dtype=np.uint8)
        ctx = SharedAnalyticsContext(frame=frame, frame_index=0, camera_id="cam1", pipeline_id="pipe1")
        events = plugin.process(ctx)

        self.assertEqual(len(events), 0)
        self.assertEqual(plugin.stats["faces_detected"], 1)
        self.assertEqual(plugin.stats["skipped_too_small"], 1)

    def test_plugin_identified_track_emits_one_event(self):
        plugin = self._make_plugin()
        # Valid face box: 80x80 px
        plugin.detector.detections = [
            FaceDetection((20, 20, 80, 80), [(35, 40), (65, 40), (50, 55), (40, 75), (60, 75)], 0.95)
        ]

        frame = np.full((200, 200, 3), 100, dtype=np.uint8)

        all_events = []
        for i in range(5):
            ctx = SharedAnalyticsContext(frame=frame.copy(), frame_index=i, camera_id="cam1", pipeline_id="pipe1")
            events = plugin.process(ctx)
            all_events.extend(events)

        # Consensus is reached at frame 3 (consensus_frames=3), emits exactly 1 event
        self.assertEqual(len(all_events), 1)
        ev = all_events[0]
        self.assertEqual(ev.event_type, "FACE_IDENTIFIED")
        self.assertEqual(ev.attributes["person_id"], "P0001")
        self.assertEqual(ev.attributes["full_name"], "Alice Smith")
        self.assertIn("similarity", ev.attributes)
        self.assertIn("margin", ev.attributes)
        self.assertIn("matched_frames", ev.attributes)
        self.assertIn("face_width_px", ev.attributes)
        self.assertIn("face_quality", ev.attributes)
        self.assertIn("face_box", ev.attributes)
        self.assertEqual(ev.attributes["metadata"], {"dept": "Eng"})

    def test_plugin_unknown_tracks_emit_nothing_when_emit_unknown_false(self):
        plugin = self._make_plugin(emit_unknown=False)
        # Face embedder produces orthogonal vector -> match score 0.0
        v_diff = np.zeros(128, dtype=np.float32)
        v_diff[10] = 1.0
        plugin.embedder = FakeFaceEmbedder(constant_vector=v_diff)
        plugin.detector.detections = [
            FaceDetection((20, 20, 80, 80), [(35, 40), (65, 40), (50, 55), (40, 75), (60, 75)], 0.95)
        ]

        frame = np.full((200, 200, 3), 100, dtype=np.uint8)
        all_events = []
        for i in range(5):
            ctx = SharedAnalyticsContext(frame=frame.copy(), frame_index=i, camera_id="cam1", pipeline_id="pipe1")
            events = plugin.process(ctx)
            all_events.extend(events)

        self.assertEqual(len(all_events), 0)


class TestFaceViewerOverlay(unittest.TestCase):
    """Viewer overlay builder and renderer tests."""

    def test_face_matches_reaches_builder(self):
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
                "face_matches": [
                    {
                        "track_id": 1,
                        "bbox": [50, 60, 150, 160],
                        "label": "Alice (P0001) 0.85",
                        "person_id": "P0001",
                        "similarity": 0.85,
                        "state": "identified",
                    }
                ]
            },
        )

        pres = FramePresentationBuilder.build(frame=ingested_frame, camera=camera, frame_context=ctx)
        self.assertEqual(len(pres.face_boxes), 1)
        fb = pres.face_boxes[0]
        self.assertIsInstance(fb, PresentedFaceBox)
        self.assertEqual(fb.track_id, 1)
        self.assertEqual(fb.x1, 50)
        self.assertEqual(fb.y1, 60)
        self.assertEqual(fb.x2, 150)
        self.assertEqual(fb.y2, 160)
        self.assertEqual(fb.state, "identified")
        self.assertEqual(fb.color_rgb, (0, 255, 0))

    def test_overlay_renderer_draws_face_box(self):
        image = np.zeros((480, 640, 3), dtype=np.uint8)
        fb = PresentedFaceBox(
            track_id=1,
            x1=50,
            y1=60,
            x2=150,
            y2=160,
            label="Alice (P0001) 0.85",
            person_id="P0001",
            similarity=0.85,
            state="identified",
            color_rgb=(0, 255, 0),
        )

        pres = FramePresentation(
            camera_id="cam_test",
            camera_name="Test Camera",
            frame_number=1,
            timestamp=100.0,
            image=image,
            face_boxes=(fb,),
        )

        renderer = OverlayRenderer(options=RenderOptions(show_faces=True))
        canvas = renderer.render(pres)
        self.assertGreater(np.sum(canvas), 0)

        # When show_faces is False, face box is not drawn
        renderer_no_faces = OverlayRenderer(options=RenderOptions(show_faces=False, draw_faces=False))
        canvas_clean = renderer_no_faces.render(pres)
        self.assertEqual(np.sum(canvas_clean), 0)


if __name__ == "__main__":
    unittest.main()
