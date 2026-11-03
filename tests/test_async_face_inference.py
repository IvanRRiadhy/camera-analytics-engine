"""Unit tests for Face Matching plugin asynchronous inference (SLICE C)."""

import time
import threading
import unittest
from unittest.mock import MagicMock
import numpy as np

from camera_analytics.context.unified_context import SharedAnalyticsContext
from camera_analytics.plugins.face_matching.config import FaceMatchConfig
from camera_analytics.plugins.face_matching.detector import FaceDetection
from camera_analytics.plugins.face_matching.gallery import FaceGallery, PersonMetadata
from camera_analytics.plugins.face_matching.plugin import FaceMatchingPlugin
from camera_analytics.plugins.face_matching.tracker import FaceIoUTracker
from camera_analytics.plugins.face_matching.consensus import PersonCooldownManager
from camera_analytics.plugins.framework.states import PluginState


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


class TestAsyncFaceInference(unittest.TestCase):
    """Test suite for SLICE C: async face inference in FaceMatchingPlugin."""

    def _make_plugin(self, async_inference=True, consensus_frames=1, frame_stride=1):
        config = FaceMatchConfig(
            frame_stride=frame_stride,
            min_face_px=50,
            min_quality=0.10,
            cosine_threshold=0.50,
            min_margin=0.05,
            consensus_frames=consensus_frames,
            consensus_window=10,
            track_cooldown_s=10.0,
            emit_unknown=False,
            overlay_unknown=True,
            debug_scores=True,
            async_inference=async_inference,
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

        d = FaceDetection((20, 20, 80, 80), [(30, 30), (50, 30), (40, 45), (35, 60), (45, 60)], 0.95)

        plugin.gallery = gallery
        plugin.detector = FakeFaceDetector([d])
        plugin.embedder = FakeFaceEmbedder(constant_vector=v)
        plugin.tracker = FaceIoUTracker(max_lost_strides=10)
        plugin._cooldown_manager = PersonCooldownManager(cooldown_s=10.0)
        plugin.state = PluginState.RUNNING
        return plugin

    def test_async_returns_immediately_under_inference_time(self):
        """Async process() returns immediately without waiting on slow inference."""
        plugin = self._make_plugin(async_inference=True)

        class SlowDetector:
            def detect(self, frame):
                time.sleep(0.15)
                return []

        plugin.detector = SlowDetector()
        frame = np.full((200, 200, 3), 120, dtype=np.uint8)
        ctx = SharedAnalyticsContext(frame=frame, frame_index=0, camera_id="cam1", pipeline_id="pipe1")

        t0 = time.perf_counter()
        events = plugin.process(ctx)
        elapsed = time.perf_counter() - t0

        self.assertLess(elapsed, 0.06, f"Expected process() to return fast, took {elapsed:.4f}s")
        self.assertEqual(events, [])
        plugin.stop()

    def test_events_arrive_tagged_with_frame_number(self):
        """Async worker outputs events tagged with the frame_number they originated from."""
        plugin = self._make_plugin(async_inference=True, consensus_frames=1)
        frame = np.full((200, 200, 3), 120, dtype=np.uint8)

        ctx1 = SharedAnalyticsContext(frame=frame, frame_index=42, camera_id="cam1", pipeline_id="pipe1")
        plugin.process(ctx1)

        # Wait for worker to finish processing frame 42
        deadline = time.time() + 1.0
        while time.time() < deadline:
            with plugin._output_lock:
                if len(plugin._completed_events) > 0:
                    break
            time.sleep(0.01)

        # Next process call drains completed events
        ctx2 = SharedAnalyticsContext(frame=frame, frame_index=43, camera_id="cam1", pipeline_id="pipe1")
        events = plugin.process(ctx2)

        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event.attributes["frame_number"], 42)
        self.assertEqual(getattr(event, "frame_number"), 42)
        plugin.stop()

    def test_stale_frames_replaced_not_queued(self):
        """Size-1 slot replaces stale unprocessed frames and counts async_frames_replaced."""
        plugin = self._make_plugin(async_inference=True)

        detector_entered = threading.Event()
        release_detector = threading.Event()

        class BlockingDetector:
            def detect(self, frame):
                detector_entered.set()
                release_detector.wait(timeout=2.0)
                return []

        plugin.detector = BlockingDetector()
        frame = np.full((200, 200, 3), 120, dtype=np.uint8)

        # Frame 1: Worker will pick this up and block inside detect()
        ctx1 = SharedAnalyticsContext(frame=frame, frame_index=1, camera_id="cam1", pipeline_id="pipe1")
        plugin.process(ctx1)
        self.assertTrue(detector_entered.wait(timeout=1.0), "Worker did not enter detect()")

        # Frame 2: Enqueued into slot
        ctx2 = SharedAnalyticsContext(frame=frame, frame_index=2, camera_id="cam1", pipeline_id="pipe1")
        plugin.process(ctx2)

        # Frame 3: Replaces Frame 2 in slot
        ctx3 = SharedAnalyticsContext(frame=frame, frame_index=3, camera_id="cam1", pipeline_id="pipe1")
        plugin.process(ctx3)

        # Frame 4: Replaces Frame 3 in slot
        ctx4 = SharedAnalyticsContext(frame=frame, frame_index=4, camera_id="cam1", pipeline_id="pipe1")
        plugin.process(ctx4)

        self.assertEqual(plugin.stats["async_frames_replaced"], 2)

        # Unblock worker and clean up
        release_detector.set()
        plugin.stop()

    def test_sync_mode_behaviour_unchanged(self):
        """When async_inference is False, execution is strictly synchronous and no worker thread runs."""
        plugin = self._make_plugin(async_inference=False, consensus_frames=1)
        self.assertIsNone(plugin._worker_thread)

        frame = np.full((200, 200, 3), 120, dtype=np.uint8)
        ctx = SharedAnalyticsContext(frame=frame, frame_index=10, camera_id="cam1", pipeline_id="pipe1")

        events = plugin.process(ctx)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].attributes["frame_number"], 10)
        self.assertIsNone(plugin._worker_thread)
        self.assertEqual(plugin.stats["async_frames_replaced"], 0)
        plugin.stop()

    def test_shutdown_joins_thread(self):
        """Lifecycle stop and shutdown join the worker thread cleanly without leaving it running."""
        plugin = self._make_plugin(async_inference=True)
        plugin.start()

        self.assertIsNotNone(plugin._worker_thread)
        self.assertTrue(plugin._worker_thread.is_alive())

        plugin.stop()
        self.assertIsNone(plugin._worker_thread)
        self.assertEqual(plugin.state, PluginState.STOPPED)

        # Idempotent shutdown
        plugin.shutdown()
        self.assertEqual(plugin.state, PluginState.STOPPED)

    def test_worker_exception_caught_and_does_not_stop_later_frames(self):
        """Exceptions in the background worker are logged and counted, and worker continues serving later frames."""
        plugin = self._make_plugin(async_inference=True)

        call_count = 0
        second_call_done = threading.Event()

        class FaultyDetector:
            def detect(self, frame):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise RuntimeError("Simulated detector transient fault")
                second_call_done.set()
                return []

        plugin.detector = FaultyDetector()
        frame = np.full((200, 200, 3), 120, dtype=np.uint8)

        # Process frame 1 (triggers exception in worker)
        ctx1 = SharedAnalyticsContext(frame=frame, frame_index=1, camera_id="cam1", pipeline_id="pipe1")
        plugin.process(ctx1)

        deadline = time.time() + 1.0
        while time.time() < deadline:
            if plugin.stats["async_worker_errors"] == 1:
                break
            time.sleep(0.01)

        self.assertEqual(plugin.stats["async_worker_errors"], 1)
        self.assertIsNotNone(plugin._worker_thread)
        self.assertTrue(plugin._worker_thread.is_alive(), "Worker thread died after exception")

        # Process frame 2 (should succeed)
        ctx2 = SharedAnalyticsContext(frame=frame, frame_index=2, camera_id="cam1", pipeline_id="pipe1")
        plugin.process(ctx2)

        self.assertTrue(second_call_done.wait(timeout=1.0), "Worker did not process subsequent frame")
        self.assertTrue(plugin._worker_thread.is_alive())
        plugin.stop()


if __name__ == "__main__":
    unittest.main()

