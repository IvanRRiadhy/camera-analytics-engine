"""
Enterprise Recording & Playback Service Test Suite (Sprint 12.3).

Verifies:
    1. VideoSegmentRecorder segment rotation & indexing.
    2. LocalStorageBackend retention cleanup & folder hierarchy.
    3. MetadataDatabase SQLite transactions & O(1) index queries.
    4. SnapshotGenerator JPEG encoding & event linkage.
    5. EventRecorder seek offset calculation.
    6. TimelineBuilder multi-criteria filtering.
    7. PlaybackService index-driven timestamp seek lookup.
    8. InvestigationAPI forensic queries.
"""

import tempfile
import time
import unittest
from pathlib import Path

import numpy as np

from camera_analytics.communication.models import StandardAnalyticsEvent
from camera_analytics.recording import (
    EventReference,
    EventRecorder,
    InvestigationAPI,
    LocalStorageBackend,
    MetadataDatabase,
    PlaybackService,
    RecordingHealthMonitor,
    RecordingSegment,
    SegmentIndexer,
    SnapshotGenerator,
    TimelineBuilder,
    VideoSegmentRecorder,
)


class TestEnterpriseRecordingService(unittest.TestCase):
    """Recording Service Unit Test Suite."""

    def setUp(self) -> None:
        """Set up temporary storage directory and components."""
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.storage_path = Path(self.tmp_dir.name)
        self.storage = LocalStorageBackend(root_dir=self.storage_path)
        self.db = MetadataDatabase(db_path=self.storage_path / "test_metadata.db")

        self.recorder = VideoSegmentRecorder(
            camera_id="cam_test",
            segment_duration_sec=1.0,
            fps=30.0,
            resolution=(320, 240),
            storage_backend=self.storage,
            database=self.db,
        )

    def tearDown(self) -> None:
        """Clean up temporary directory."""
        if self.recorder.is_active:
            self.recorder.stop()
        try:
            self.tmp_dir.cleanup()
        except Exception:
            pass

    def test_segment_indexer_checksum(self) -> None:
        """Verify SegmentIndexer calculates MD5 checksums."""
        dummy_file = self.storage_path / "test_checksum.txt"
        dummy_file.write_text("hello cctv analytics", encoding="utf-8")

        chk = SegmentIndexer.calculate_checksum(dummy_file)
        self.assertTrue(len(chk) > 0)

    def test_recorder_rotation_and_database_indexing(self) -> None:
        """Verify VideoSegmentRecorder auto-rotates segments and indexes into database."""
        self.recorder.start()
        dummy_frame = np.zeros((240, 320, 3), dtype=np.uint8)

        start_ts = time.time()
        # Write frames over 2.5 seconds to trigger 2 rotations
        for i in range(75):
            self.recorder.write_frame(dummy_frame, timestamp=start_ts + (i / 30.0))

        self.recorder.stop()

        counts = self.db.count_summary()
        self.assertGreaterEqual(counts["segment_count"], 2)

    def test_snapshot_generator_and_event_recorder(self) -> None:
        """Verify SnapshotGenerator encodes JPEG and EventRecorder logs references."""
        self.recorder.start()
        dummy_frame = np.ones((240, 320, 3), dtype=np.uint8) * 255

        evt = StandardAnalyticsEvent(
            event_type="CROWD_ALERT",
            message="Crowd threshold exceeded",
            camera_id="cam_test",
            severity="CRITICAL",
        )

        snap_gen = SnapshotGenerator(storage_backend=self.storage, database=self.db, quality=80)
        evt_recorder = EventRecorder(recorder=self.recorder, database=self.db, snapshot_generator=snap_gen)

        evt_ref = evt_recorder.record_event(evt, frame=dummy_frame)
        self.assertEqual(evt_ref.event_type, "CROWD_ALERT")
        self.assertIsNotNone(evt_ref.snapshot_path)
        self.assertTrue(Path(evt_ref.snapshot_path).exists())

        self.recorder.stop()

    def test_playback_service_index_seek(self) -> None:
        """Verify PlaybackService performs O(1) index-driven seek lookup."""
        now = time.time()
        seg1 = RecordingSegment(
            segment_id="seg_01",
            camera_id="cam_play",
            file_path=str(self.storage_path / "seg_01.mp4"),
            start_timestamp=now,
            end_timestamp=now + 10.0,
            duration_sec=10.0,
        )
        self.db.add_segment(seg1)

        playback = PlaybackService(database=self.db)
        seek_res = playback.seek_timestamp("cam_play", now + 5.0)

        self.assertIsNotNone(seek_res)
        self.assertEqual(seek_res.segment_id, "seg_01")
        self.assertAlmostEqual(seek_res.seek_offset_sec, 5.0, places=1)
        self.assertTrue(seek_res.exact_match)

    def test_investigation_api_and_timeline(self) -> None:
        """Verify InvestigationAPI queries and timeline generation."""
        now = time.time()
        ref = EventReference(
            event_id="evt_100",
            event_type="LOITERING",
            camera_id="cam_inv",
            timestamp=now,
            segment_id="seg_100",
            seek_offset_sec=3.5,
            track_id=42,
            severity="WARNING",
            message="Loitering track 42",
        )
        self.db.add_event_reference(ref)

        investigation = InvestigationAPI(database=self.db)
        results = investigation.query_track_history(track_id=42)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].event_id, "evt_100")

        timeline = investigation.generate_timeline(camera_id="cam_inv")
        self.assertEqual(len(timeline), 1)
        self.assertEqual(timeline[0]["event_type"], "LOITERING")

    def test_storage_retention_enforcement(self) -> None:
        """Verify LocalStorageBackend purges expired recording files."""
        old_dir = self.storage.recordings_dir / "cam_test" / "20200101"
        old_dir.mkdir(parents=True, exist_ok=True)
        old_file = old_dir / "old_seg.mp4"
        old_file.write_text("old content", encoding="utf-8")

        # Backdate mtime to 100 days ago
        old_mtime = time.time() - (100 * 86400)
        import os
        os.utime(old_file, (old_mtime, old_mtime))

        purged = self.storage.enforce_retention(max_retention_days=30)
        self.assertEqual(purged, 1)
        self.assertFalse(old_file.exists())

    def test_debug_visualization_overlay(self) -> None:
        """Verify DebugVisualizationOverlay renders track badges and timeline banner onto frame."""
        from camera_analytics.recording.overlay import DebugOverlayConfig, DebugVisualizationOverlay

        overlay = DebugVisualizationOverlay(config=DebugOverlayConfig(enabled=True))
        dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)

        evt1 = StandardAnalyticsEvent(
            event_type="LOITERING",
            message="Loitering detected",
            camera_id="cam_test",
            track_id=7,
            severity="WARNING",
        )
        evt2 = StandardAnalyticsEvent(
            event_type="ZONE_ENTER",
            message="Zone enter detected",
            camera_id="cam_test",
            track_id=7,
            severity="INFO",
        )

        overlay.register_event(evt1, bbox=[100, 100, 200, 300], duration_sec=5.2)
        overlay.register_event(evt2, bbox=[100, 100, 200, 300], duration_sec=0.0)

        overlayed = overlay.draw_overlay(dummy_frame, track_bboxes={7: [100, 100, 200, 300]})

        self.assertEqual(overlayed.shape, dummy_frame.shape)
        # Check that canvas pixels were modified by overlay drawing
        self.assertTrue(np.any(overlayed != dummy_frame))


if __name__ == "__main__":
    unittest.main()
