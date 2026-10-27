import unittest
import numpy as np
import time

from camera_analytics.plugins.framework.context import PluginContext
from camera_analytics.plugins.framework.states import PluginState
from camera_analytics.context.unified_context import SharedAnalyticsContext
from camera_analytics.communication.models import AnalyticsEventSerializer
from camera_analytics.plugins.vehicle_lpr.plugin import VehicleLPRPlugin
from camera_analytics.plugins.vehicle_lpr.config import VehicleLPRConfig
from camera_analytics.plugins.vehicle_lpr.tracker import PlateIoUTracker
from camera_analytics.plugins.vehicle_lpr.model_cache import SharedModelCache
from anpr_v2.reader import ReaderOutput


class StubPlateDetector:
    def __init__(self, boxes=None):
        self.boxes_to_return = boxes or []

    def predict(self, source, **kwargs):
        class BoxItem:
            def __init__(self, xyxy, conf):
                import torch
                self.xyxy = torch.tensor([xyxy])
                self.conf = torch.tensor([conf])

        class ResultItem:
            def __init__(self, boxes):
                self.boxes = boxes

        boxes = [BoxItem(b[:4], b[4]) for b in self.boxes_to_return]
        return [ResultItem(boxes)]


class StubCharReader:
    def __init__(self, raw_text="B1234ABC", status="GRAMMAR_VALID", grammar_valid=True, mean_box_conf_all=0.88):
        self.raw_text = raw_text
        self.status = status
        self.grammar_valid = grammar_valid
        self.mean_box_conf_all = mean_box_conf_all

    def read(self, image_input):
        return ReaderOutput(
            raw_text=self.raw_text,
            status=self.status,
            grammar_valid=self.grammar_valid,
            branch="single_row",
            n_boxes=8,
            dedup_removals=0,
            char_box_confs=[0.90, 0.88, 0.85, 0.92, 0.89, 0.91, 0.87, 0.86],
            min_box_conf_all=0.85,
            mean_box_conf_all=self.mean_box_conf_all,
            raw_y_ratio=0.1,
            corrected_y_ratio=0.1,
            height_ratios=[1.0] * 8,
            edge_distances=[0.05] * 8,
            raw_boxes=[],
            engines={},
        )


class TestVehicleLPRPluginUnit(unittest.TestCase):
    def setUp(self):
        SharedModelCache._detector_cache.clear()
        SharedModelCache._reader_cache.clear()
        SharedModelCache._ref_counts = {"detector": 0, "reader": 0}

    def test_lifecycle_and_model_sharing(self):
        """Two pipeline plugin instances share one cached detector and reader."""
        stub_det = StubPlateDetector([(100, 100, 300, 150, 0.9)])
        stub_reader = StubCharReader()

        # Pre-seed cache
        SharedModelCache._detector_cache[(r"E:\ANPR\runs\detect\indonesian_plate_yolo26_v1\weights\best.pt", "cpu", 640, 0.25)] = stub_det
        SharedModelCache._reader_cache[(r"E:\ANPR\runs\detect\lprd_yolo26n_320\weights\last.pt", "cpu", 320, 0.02)] = stub_reader

        p1 = VehicleLPRPlugin(name="Vehicle LPR")
        ctx1 = PluginContext(pipeline_id="pipeline_cam_1", camera_id="cam_1")
        ctx1.config = {"device": "cpu"}
        self.assertTrue(p1.initialize(ctx1))
        self.assertEqual(SharedModelCache._ref_counts["detector"], 1)
        self.assertEqual(SharedModelCache._ref_counts["reader"], 1)

        p2 = VehicleLPRPlugin(name="Vehicle LPR")
        ctx2 = PluginContext(pipeline_id="pipeline_cam_2", camera_id="cam_2")
        ctx2.config = {"device": "cpu"}
        self.assertTrue(p2.initialize(ctx2))
        self.assertEqual(SharedModelCache._ref_counts["detector"], 2)
        self.assertEqual(SharedModelCache._ref_counts["reader"], 2)

        # Shutdown p1
        p1.shutdown()
        self.assertEqual(SharedModelCache._ref_counts["detector"], 1)
        self.assertEqual(SharedModelCache._ref_counts["reader"], 1)

        # Shutdown p2 releases completely
        p2.shutdown()
        self.assertEqual(SharedModelCache._ref_counts["detector"], 0)
        self.assertEqual(SharedModelCache._ref_counts["reader"], 0)
        self.assertEqual(len(SharedModelCache._detector_cache), 0)
        self.assertEqual(len(SharedModelCache._reader_cache), 0)

    def test_plugin_manager_stop_all_calls_shutdown_and_clears_refcounts(self):
        """Verify PluginManager.stop_all() calls plugin.shutdown() and decrements SharedModelCache refcounts to 0."""
        from camera_analytics.plugins.framework.manager import PluginManager

        stub_det = StubPlateDetector([(100, 100, 300, 150, 0.9)])
        stub_reader = StubCharReader()
        SharedModelCache._detector_cache[(r"E:\ANPR\runs\detect\indonesian_plate_yolo26_v1\weights\best.pt", "cpu", 640, 0.25)] = stub_det
        SharedModelCache._reader_cache[(r"E:\ANPR\runs\detect\lprd_yolo26n_320\weights\last.pt", "cpu", 320, 0.02)] = stub_reader

        mgr1 = PluginManager(pipeline_id="pipeline_cam_1")
        ctx1 = PluginContext(pipeline_id="pipeline_cam_1", camera_id="cam_1", config={"device": "cpu"})
        p1 = mgr1.load_plugin("camera_analytics.plugins.vehicle_lpr.plugin", "Vehicle Lpr", ctx1)
        self.assertIsNotNone(p1)

        mgr2 = PluginManager(pipeline_id="pipeline_cam_2")
        ctx2 = PluginContext(pipeline_id="pipeline_cam_2", camera_id="cam_2", config={"device": "cpu"})
        p2 = mgr2.load_plugin("camera_analytics.plugins.vehicle_lpr.plugin", "Vehicle Lpr", ctx2)
        self.assertIsNotNone(p2)

        self.assertEqual(SharedModelCache._ref_counts["detector"], 2)
        self.assertEqual(SharedModelCache._ref_counts["reader"], 2)

        # Calling stop() directly on plugin only clears track/voting state, NOT model refcounts
        p1.stop()
        self.assertEqual(p1.state, PluginState.STOPPED)
        self.assertEqual(SharedModelCache._ref_counts["detector"], 2)
        self.assertEqual(SharedModelCache._ref_counts["reader"], 2)

        # PluginManager.stop_all() calls plugin.shutdown(), decrementing refcounts and clearing cache at 0
        mgr1.stop_all()
        self.assertEqual(SharedModelCache._ref_counts["detector"], 1)
        self.assertEqual(SharedModelCache._ref_counts["reader"], 1)
        self.assertIsNone(p1.detector)
        self.assertIsNone(p1.reader)

        mgr2.stop_all()
        self.assertEqual(SharedModelCache._ref_counts["detector"], 0)
        self.assertEqual(SharedModelCache._ref_counts["reader"], 0)
        self.assertEqual(len(SharedModelCache._detector_cache), 0)
        self.assertEqual(len(SharedModelCache._reader_cache), 0)
        self.assertIsNone(p2.detector)
        self.assertIsNone(p2.reader)

    def test_detection_voting_and_event_serialization(self):
        """End-to-end event emission without numpy types leaking."""
        plugin = VehicleLPRPlugin(name="Vehicle LPR")
        ctx = PluginContext(pipeline_id="pipeline_test", camera_id="cam_test")
        ctx.config = {
            "mode": "detector",
            "device": "cpu",
            "min_observations": 2,
            "min_plate_width_px": 50.0,
            "min_sharpness": 5.0,
            "frame_stride": 1,
        }
        plugin.initialize(ctx)
        plugin.state = PluginState.RUNNING

        # Inject stubs
        plugin.detector = StubPlateDetector([(100, 100, 300, 160, 0.95)])
        plugin.reader = StubCharReader(raw_text="B1234ABC", mean_box_conf_all=0.91)

        # Create 1080p frame with a realistic high-contrast rectangle
        frame = np.ones((720, 1280, 3), dtype=np.uint8) * 128
        # Add high contrast pattern inside plate crop to satisfy sharpness and brightness filters
        frame[100:160, 100:300] = 200
        for x in range(110, 290, 10):
            frame[110:150, x:x+5] = 20

        # Frame 1: Observation 1
        f_ctx1 = SharedAnalyticsContext(frame=frame, frame_index=0, camera_id="cam_test", pipeline_id="pipeline_test", timestamp_utc=100.0)
        evts1 = plugin.process(f_ctx1)
        self.assertEqual(len(evts1), 0)  # Requires min_observations=2

        # Frame 2: Observation 2 -> Consensus reached
        f_ctx2 = SharedAnalyticsContext(frame=frame, frame_index=1, camera_id="cam_test", pipeline_id="pipeline_test", timestamp_utc=100.1)
        evts2 = plugin.process(f_ctx2)
        self.assertEqual(len(evts2), 1)

        evt = evts2[0]
        self.assertEqual(evt.event_type, "VEHICLE_LPR")
        self.assertEqual(evt.plugin_name, "Vehicle LPR")
        self.assertEqual(evt.attributes["plate_text"], "B1234ABC")
        self.assertEqual(evt.attributes["status"], "GRAMMAR_VALID")
        self.assertAlmostEqual(evt.confidence, 0.91, places=2)

        # Check that attributes are strictly native Python types
        for k, v in evt.attributes.items():
            if isinstance(v, list):
                for item in v:
                    self.assertIsInstance(item, (int, float, str, bool))
            else:
                self.assertIsInstance(v, (int, float, str, bool, type(None)))

        # Verify serialization
        serialized = AnalyticsEventSerializer.serialize(evt)
        self.assertIn('"plate_text":"B1234ABC"', serialized)
        self.assertIn('"status":"GRAMMAR_VALID"', serialized)

        # Frame 3: Track has emitted and cooldown prevents duplicate emission
        f_ctx3 = SharedAnalyticsContext(frame=frame, frame_index=2, camera_id="cam_test", pipeline_id="pipeline_test", timestamp_utc=100.2)
        evts3 = plugin.process(f_ctx3)
        self.assertEqual(len(evts3), 0)

        plugin.shutdown()

    def test_bad_frame_and_exception_handling(self):
        """Plugin does not raise on empty frames or detector failures."""
        plugin = VehicleLPRPlugin(name="Vehicle LPR")
        ctx = PluginContext(pipeline_id="pipeline_test", camera_id="cam_test")
        plugin.initialize(ctx)
        plugin.state = PluginState.RUNNING

        # None frame
        evts = plugin.process(SharedAnalyticsContext(frame=None))
        self.assertEqual(evts, [])

        # Empty array
        evts = plugin.process(SharedAnalyticsContext(frame=np.empty((0, 0, 3), dtype=np.uint8)))
        self.assertEqual(evts, [])

        # Faulty detector raising runtime exception
        class CrashingDetector:
            def predict(self, *args, **kwargs):
                raise RuntimeError("CUDA out of memory stub")

        plugin.detector = CrashingDetector()
        f_ctx = SharedAnalyticsContext(frame=np.zeros((100, 100, 3), dtype=np.uint8), frame_index=0)
        evts = plugin.process(f_ctx)
        self.assertEqual(evts, [])
        # Plugin state must NOT transition to FAILED
        self.assertEqual(plugin.state, PluginState.RUNNING)

        plugin.shutdown()

    def test_failure_isolation(self):
        """Phase 4b Item 3: Failure isolation tests ensuring initialize() returns False and cleans up refcounts."""
        from unittest.mock import patch

        # 1. Detector weights missing
        p_det = VehicleLPRPlugin(name="Vehicle LPR")
        ctx_det = PluginContext(pipeline_id="pipe_err_det", camera_id="cam_err_det")
        ctx_det.config = {"detector_weights": r"E:\ANPR\non_existent_det.pt", "device": "cpu"}
        self.assertFalse(p_det.initialize(ctx_det))
        self.assertEqual(p_det.state, PluginState.FAILED)
        self.assertEqual(SharedModelCache._ref_counts["detector"], 0)
        self.assertEqual(SharedModelCache._ref_counts["reader"], 0)

        # 2. Reader weights missing
        p_rdr = VehicleLPRPlugin(name="Vehicle LPR")
        ctx_rdr = PluginContext(pipeline_id="pipe_err_rdr", camera_id="cam_err_rdr")
        ctx_rdr.config = {"reader_weights": r"E:\ANPR\non_existent_rdr.pt", "device": "cpu"}
        self.assertFalse(p_rdr.initialize(ctx_rdr))
        self.assertEqual(p_rdr.state, PluginState.FAILED)
        self.assertEqual(SharedModelCache._ref_counts["detector"], 0)
        self.assertEqual(SharedModelCache._ref_counts["reader"], 0)

        # 3. Reader SHA256 mismatch
        p_sha = VehicleLPRPlugin(name="Vehicle LPR")
        ctx_sha = PluginContext(pipeline_id="pipe_err_sha", camera_id="cam_err_sha")
        ctx_sha.config = {"expected_sha256": "0000000000000000000000000000000000000000000000000000000000000000", "device": "cpu"}
        self.assertFalse(p_sha.initialize(ctx_sha))
        self.assertEqual(p_sha.state, PluginState.FAILED)
        self.assertEqual(SharedModelCache._ref_counts["detector"], 0)
        self.assertEqual(SharedModelCache._ref_counts["reader"], 0)

        # 4. anpr_v2 import error
        p_imp = VehicleLPRPlugin(name="Vehicle LPR")
        ctx_imp = PluginContext(pipeline_id="pipe_err_imp", camera_id="cam_err_imp")
        with patch.dict("sys.modules", {"anpr_v2.reader": None}):
            with patch("anpr_v2.reader.CharDetectorReader", side_effect=ImportError("Simulated anpr_v2 import error")):
                self.assertFalse(p_imp.initialize(ctx_imp))
                self.assertEqual(p_imp.state, PluginState.FAILED)
        self.assertEqual(SharedModelCache._ref_counts["detector"], 0)
        self.assertEqual(SharedModelCache._ref_counts["reader"], 0)

        # 5. CUDA unavailable simulation
        p_cuda = VehicleLPRPlugin(name="Vehicle LPR")
        ctx_cuda = PluginContext(pipeline_id="pipe_err_cuda", camera_id="cam_err_cuda")
        ctx_cuda.config = {"device": "cuda:99"}
        with patch("torch.cuda.is_available", return_value=False):
            with patch("ultralytics.YOLO", side_effect=RuntimeError("CUDA device unavailable")):
                self.assertFalse(p_cuda.initialize(ctx_cuda))
                self.assertEqual(p_cuda.state, PluginState.FAILED)
        self.assertEqual(SharedModelCache._ref_counts["detector"], 0)
        self.assertEqual(SharedModelCache._ref_counts["reader"], 0)

    def test_counter_reconciliation(self):
        """Phase 4b Item 4: Assert detections_total exactly reconciles with skip buckets and reader results."""
        plugin = VehicleLPRPlugin(name="Vehicle LPR")
        ctx = PluginContext(pipeline_id="pipe_reconcile", camera_id="cam_reconcile")
        ctx.config = {
            "mode": "detector",
            "device": "cpu",
            "frame_stride": 1,
            "min_plate_width_px": 50.0,
            "min_sharpness": 10.0,
            "min_brightness": 20.0,
            "max_brightness": 240.0,
        }
        plugin.initialize(ctx)
        plugin.state = PluginState.RUNNING

        # Simulate 6 detections across frames with different outcomes:
        # Det 1: too small (<50px width)
        # Det 2: too blurry
        # Det 3: too dark
        # Det 4: lock timeout
        # Det 5: reader_no_read
        # Det 6: reader_ok
        stub_det = StubPlateDetector([
            (10, 10, 40, 40, 0.9),       # Det 1: width=30 < 50 -> too_small
            (50, 100, 150, 150, 0.9),    # Det 2: blurry (solid 128)
            (50, 200, 150, 250, 0.9),    # Det 3: sharp but dark (< 20)
            (50, 300, 150, 350, 0.9),    # Det 4: lock timeout
            (50, 400, 150, 450, 0.9),    # Det 5: reader_no_read
            (50, 500, 150, 550, 0.9),    # Det 6: reader_ok
        ])
        plugin.detector = stub_det

        frame = np.ones((720, 1280, 3), dtype=np.uint8) * 128
        # Det 2: blurry (already flat 128, var=0)

        # Det 3: dark (values 0-15, but striped so sharpness > 10)
        frame[180:270, 30:170] = 2
        for bar in range(50, 150, 6):
            frame[200:250, bar:bar+2] = 16

        # Det 4, 5, 6: sharp and normal brightness
        for y_top in (300, 400, 500):
            frame[y_top-20:y_top+70, 30:170] = 200
            for bar in range(60, 140, 8):
                frame[y_top+5:y_top+45, bar:bar+4] = 20

        # Reader behavior stub
        reader_call_count = 0
        def stub_read(crop):
            nonlocal reader_call_count
            reader_call_count += 1
            if reader_call_count == 2:
                # First reader call is det 5 (since det 4 will hit lock timeout) -> NO_READ
                return StubCharReader(status="NO_READ", raw_text="").read(crop)
            # Second reader call is det 6 -> GRAMMAR_VALID
            return StubCharReader(status="GRAMMAR_VALID", raw_text="B1234ABC").read(crop)

        class CustomReader:
            def read(self, crop):
                return stub_read(crop)

        plugin.reader = CustomReader()

        # Mock lock acquisition on reader: fail on the 1st attempt (det 4) to produce lock timeout
        orig_lock = SharedModelCache.reader_inference_lock
        acquire_count = 0

        class MockLock:
            def acquire(self, timeout=None):
                nonlocal acquire_count
                acquire_count += 1
                if acquire_count == 1:
                    return False
                return orig_lock.acquire(timeout=timeout)

            def release(self):
                orig_lock.release()

        SharedModelCache.reader_inference_lock = MockLock()
        try:
            f_ctx = SharedAnalyticsContext(frame=frame, frame_index=0, camera_id="cam_reconcile", pipeline_id="pipe_reconcile", timestamp_utc=1.0)
            plugin.process(f_ctx)
        finally:
            SharedModelCache.reader_inference_lock = orig_lock

        stats = plugin.get_stats()
        # Verify strict mutually exclusive reconciliation equation (skipped_cooldown is outside the sum):
        bucket_sum = (
            stats["skipped_too_small"]
            + stats["skipped_too_blurry"]
            + stats["skipped_too_dark"]
            + stats["skipped_lock_timeout"]
            + stats["skipped_after_consensus"]
            + stats["reader_no_read"]
            + stats["reader_ok"]
        )
        self.assertEqual(stats["detections_total"], 6)
        self.assertEqual(stats["detections_total"], bucket_sum)
        # Verify that cooldown is reported as a separate sub-counter outside detections_total partition
        self.assertIn("skipped_cooldown", stats)
        self.assertEqual(stats["skipped_too_small"], 1)
        self.assertEqual(stats["skipped_too_blurry"], 1)
        self.assertEqual(stats["skipped_too_dark"], 1)
        self.assertEqual(stats["skipped_lock_timeout"], 1)
        self.assertEqual(stats["reader_no_read"], 1)
        self.assertEqual(stats["reader_ok"], 1)

        plugin.shutdown()

    def test_localizer_duplicate_box_deduplication(self):
        """Test same-frame duplicate plate box deduplication (IoU 0.95 suppressed)."""
        from camera_analytics.plugins.vehicle_lpr.localizer import PlateLocalizer
        localizer = PlateLocalizer()

        # Two overlapping boxes with IoU ~ 0.95
        box1 = (100.0, 100.0, 300.0, 200.0, 0.90)
        box2 = (101.0, 101.0, 300.0, 200.0, 0.80)
        # One disjoint box
        box3 = (400.0, 100.0, 600.0, 200.0, 0.85)

        deduped = localizer.deduplicate_boxes([box1, box2, box3], iou_threshold=0.50)
        self.assertEqual(len(deduped), 2)
        # Higher confidence box1 kept, box2 dropped
        self.assertEqual(deduped[0][4], 0.90)
        self.assertEqual(deduped[1][4], 0.85)

    def test_tracker_moving_box_and_one_to_one_assignment(self):
        """Test PlateIoUTracker with moving box across strides and strict one-to-one track assignment."""
        from camera_analytics.plugins.vehicle_lpr.tracker import PlateIoUTracker
        tracker = PlateIoUTracker(max_lost_strides=5, min_iou=0.30)

        # Simulate vehicle moving horizontally at 15px per stride
        # Frame 0
        b0 = [(100.0, 100.0, 250.0, 180.0, 0.90)]
        up0, _ = tracker.update(b0, frame_idx=0)
        self.assertEqual(len(up0), 1)
        t0 = up0[0][0]
        self.assertEqual(t0.track_id, 1)

        # Frame 3: Moved by 15px
        b1 = [(115.0, 100.0, 265.0, 180.0, 0.90)]
        up1, _ = tracker.update(b1, frame_idx=3)
        self.assertEqual(len(up1), 1)
        self.assertEqual(up1[0][0].track_id, 1)

        # Frame 6: Two detections presented in same frame (e.g. if one were unsuppressed)
        # One-to-one matching must ensure Track 1 takes at most ONE detection
        b2 = [
            (130.0, 100.0, 280.0, 180.0, 0.90),
            (128.0, 102.0, 278.0, 182.0, 0.80),
        ]
        up2, _ = tracker.update(b2, frame_idx=6)
        self.assertEqual(len(up2), 2)
        t_ids = [p[0].track_id for p in up2]
        self.assertIn(1, t_ids)
        # Second box becomes Track 2 because Track 1 can only take one box
        self.assertIn(2, t_ids)

    def test_plugin_name_constant_and_clean_attributes(self):
        """B.1 and B.6: Ensure plugin_name is constant 'Vehicle LPR' and no duplicate char_confs key."""
        plugin = VehicleLPRPlugin()
        plugin.state = PluginState.RUNNING
        plugin.config.min_observations = 1
        plugin.config.min_winner_share = 0.50
        plugin.config.min_plate_width_px = 50.0
        plugin.config.min_sharpness = 1.0
        plugin.config.min_brightness = 10.0
        plugin.config.max_brightness = 250.0

        box = (100.0, 100.0, 300.0, 180.0, 0.95)
        plugin.detector = StubPlateDetector(boxes=[box])
        plugin.reader = StubCharReader(raw_text="B1234ABC", status="GRAMMAR_VALID")

        frame = np.ones((720, 1280, 3), dtype=np.uint8) * 128
        frame[100:180, 100:300] = 200
        for b in range(120, 280, 10):
            frame[110:170, b:b+5] = 20

        ctx = SharedAnalyticsContext(frame=frame, frame_index=0, camera_id="cam_b1", pipeline_id="pipe_b1")
        events = plugin.process(ctx)
        self.assertEqual(len(events), 1)
        evt = events[0]
        self.assertEqual(evt.plugin_name, "Vehicle LPR")
        self.assertEqual(evt.event_type, "VEHICLE_LPR")
        self.assertIn("char_confidences", evt.attributes)
        self.assertNotIn("char_confs", evt.attributes)
        self.assertEqual(evt.track_id, 1)

    def test_stationary_plate_ten_strided_frames_one_track(self):
        """B.2: Verify a stationary plate across 10 strided frames stays ONE track starting at 1."""
        from camera_analytics.plugins.vehicle_lpr.tracker import PlateIoUTracker
        tracker = PlateIoUTracker(max_lost_strides=10)
        box = (100.0, 100.0, 300.0, 180.0, 0.95)

        for stride_idx in range(10):
            frame_idx = stride_idx * 3
            updated_pairs, expired = tracker.update([box], frame_idx)
            self.assertEqual(len(updated_pairs), 1)
            track, is_updated = updated_pairs[0]
            self.assertTrue(is_updated)
            self.assertEqual(track.track_id, 1)
            self.assertEqual(len(expired), 0)

        self.assertEqual(len(tracker.tracks), 1)
        self.assertEqual(tracker.tracks[1].hits, 10)
        self.assertEqual(tracker.next_track_id, 2)

    def test_voting_tie_consensus_and_expiry(self):
        """B.5: Test voting tie never emits, consensus requires > 0.50 share and >= 3 obs, and expiry emits once."""
        plugin = VehicleLPRPlugin()
        plugin.state = PluginState.RUNNING
        plugin.config.min_observations = 3
        plugin.config.min_winner_share = 0.50
        plugin.config.emit_on_track_expiry = True
        plugin.config.min_plate_width_px = 50.0
        plugin.config.min_sharpness = 1.0
        plugin.config.min_brightness = 10.0
        plugin.config.max_brightness = 250.0

        box = (100.0, 100.0, 300.0, 180.0, 0.95)
        plugin.detector = StubPlateDetector(boxes=[box])

        frame = np.ones((720, 1280, 3), dtype=np.uint8) * 128
        frame[100:180, 100:300] = 200
        for b in range(120, 280, 10):
            frame[110:170, b:b+5] = 20

        # Frame 0: observation 1 -> 'B1234ABC' (1 vote)
        plugin.reader = StubCharReader(raw_text="B1234ABC")
        evts = plugin.process(SharedAnalyticsContext(frame=frame, frame_index=0, camera_id="cam_test", pipeline_id="pipe_test"))
        self.assertEqual(len(evts), 0)

        # Frame 3: observation 2 -> 'D5678XYZ' (1:1 tie -> winner_share 0.50, must NOT emit)
        plugin.reader = StubCharReader(raw_text="D5678XYZ")
        evts = plugin.process(SharedAnalyticsContext(frame=frame, frame_index=3, camera_id="cam_test", pipeline_id="pipe_test"))
        self.assertEqual(len(evts), 0)

        # Frame 6: observation 3 -> 'B1234ABC' (2 'B1234ABC', 1 'D5678XYZ' -> 2/3 = 0.667 > 0.50, obs=3 >= 3 -> EMIT)
        plugin.reader = StubCharReader(raw_text="B1234ABC")
        evts = plugin.process(SharedAnalyticsContext(frame=frame, frame_index=6, camera_id="cam_test", pipeline_id="pipe_test"))
        self.assertEqual(len(evts), 1)
        self.assertEqual(evts[0].attributes["plate_text"], "B1234ABC")
        self.assertEqual(evts[0].attributes["winner_share"], 0.6667)
        self.assertFalse(evts[0].attributes.get("finalized_on_expiry", False))

        # Now test track expiry emission on another track that doesn't reach consensus before losing track
        plugin2 = VehicleLPRPlugin()
        plugin2.state = PluginState.RUNNING
        plugin2.config.min_observations = 3
        plugin2.config.min_winner_share = 0.50
        plugin2.config.emit_on_track_expiry = True
        plugin2.config.min_plate_width_px = 50.0
        plugin2.config.min_sharpness = 1.0
        plugin2.config.min_brightness = 10.0
        plugin2.config.max_brightness = 250.0
        plugin2.tracker = PlateIoUTracker(max_lost_strides=2)

        # Feed 3 observations that don't reach strict > 0.50 consensus:
        # Obs 1: B1234AA, Obs 2: B1234BB, Obs 3: B1234CC (1:1:1 tie, winner_share = 0.33)
        # But for expiry, let's test a valid winner with >= 3 obs: 3 votes of 'L1048BU', but suppose winner_share threshold was 0.80
        plugin2.config.min_winner_share = 0.80
        # Obs 1: L1048BU, Obs 2: L1048BU, Obs 3: L1018BU (2/3 = 0.67 < 0.80 -> no live consensus)
        box2 = (50.0, 50.0, 200.0, 120.0, 0.90)
        plugin2.detector = StubPlateDetector(boxes=[box2])

        plugin2.reader = StubCharReader(raw_text="L1048BU")
        evts = plugin2.process(SharedAnalyticsContext(frame=frame, frame_index=0, camera_id="cam_exp", pipeline_id="pipe_exp"))
        self.assertEqual(len(evts), 0)

        plugin2.reader = StubCharReader(raw_text="L1048BU")
        evts = plugin2.process(SharedAnalyticsContext(frame=frame, frame_index=3, camera_id="cam_exp", pipeline_id="pipe_exp"))
        self.assertEqual(len(evts), 0)

        plugin2.reader = StubCharReader(raw_text="L1018BU")
        evts = plugin2.process(SharedAnalyticsContext(frame=frame, frame_index=6, camera_id="cam_exp", pipeline_id="pipe_exp"))
        self.assertEqual(len(evts), 0)

        # Now detector stops seeing plate for 3 strides (> max_lost_strides=2)
        plugin2.detector = StubPlateDetector(boxes=[])
        # Stride 1 lost
        evts = plugin2.process(SharedAnalyticsContext(frame=frame, frame_index=9, camera_id="cam_exp", pipeline_id="pipe_exp"))
        self.assertEqual(len(evts), 0)
        # Stride 2 lost
        evts = plugin2.process(SharedAnalyticsContext(frame=frame, frame_index=12, camera_id="cam_exp", pipeline_id="pipe_exp"))
        self.assertEqual(len(evts), 0)
        # Stride 3 lost -> track expires -> emit_on_track_expiry triggers!
        evts = plugin2.process(SharedAnalyticsContext(frame=frame, frame_index=15, camera_id="cam_exp", pipeline_id="pipe_exp"))
        self.assertEqual(len(evts), 1)
        self.assertEqual(evts[0].attributes["plate_text"], "L1048BU")
        self.assertTrue(evts[0].attributes["finalized_on_expiry"])
        self.assertEqual(evts[0].attributes["observation_count"], 3)
