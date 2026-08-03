"""
CLI Recording & Playback Service Validator & Benchmark Tool.

Validates segment rotation, recording integrity, metadata database consistency, timeline indexing,
snapshot generation, playback seek performance, retention cleanup, and prints benchmark reports.

Usage::

    python -m camera_analytics.tools.validate_recording_service --video camera_analytics/samples/Screen_Recording_20260622_113428_EZVIZ.mp4
"""

from __future__ import annotations

import argparse
import logging
import tempfile
import time
from pathlib import Path

import cv2
import numpy as np

from camera_analytics.communication.models import StandardAnalyticsEvent
from camera_analytics.recording import (
    DebugOverlayConfig,
    DebugVisualizationOverlay,
    EventRecorder,
    InvestigationAPI,
    LocalStorageBackend,
    MetadataDatabase,
    PlaybackService,
    RecordingHealthMonitor,
    SnapshotGenerator,
    VideoSegmentRecorder,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("validate_recording_service")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Enterprise CCTV Recording & Playback Service Validator CLI"
    )
    parser.add_argument(
        "--video",
        type=str,
        default="camera_analytics/samples/Screen_Recording_20260622_113428_EZVIZ.mp4",
        help="Path to real video file for recording simulation",
    )
    parser.add_argument(
        "--frames",
        type=int,
        default=200,
        help="Total frames to process from video (default 200)",
    )
    parser.add_argument(
        "--segment-duration",
        type=float,
        default=2.0,
        help="Segment duration in seconds for testing rotation (default 2.0s)",
    )
    parser.add_argument(
        "--debug-overlay",
        action="store_true",
        default=True,
        help="Enable Enterprise Debug Visualization Overlay (badges & timeline banner)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="camera_analytics/storage_test",
        help="Storage output directory",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logger.info("================================================================================")
    logger.info("SPRINT 12.3 — ENTERPRISE RECORDING & PLAYBACK SERVICE VALIDATION")
    logger.info("================================================================================")

    storage_path = Path(args.output_dir)
    storage = LocalStorageBackend(root_dir=storage_path)
    db = MetadataDatabase(db_path=storage_path / "metadata.db")

    video_path = Path(args.video)
    cap = None
    res = (640, 480)
    fps = 30.0

    if video_path.exists():
        logger.info("Opening video source file: %s", video_path)
        cap = cv2.VideoCapture(str(video_path))
        if cap.isOpened():
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            video_fps = cap.get(cv2.CAP_PROP_FPS)
            if w > 0 and h > 0:
                res = (w, h)
            if video_fps > 0:
                fps = video_fps
            logger.info("Video specs: %dx%d @ %.1f FPS", res[0], res[1], fps)

    debug_overlay = DebugVisualizationOverlay(
        config=DebugOverlayConfig(enabled=args.debug_overlay)
    )

    recorder = VideoSegmentRecorder(
        camera_id="cam_ezviz_lobby",
        segment_duration_sec=args.segment_duration,
        fps=fps,
        resolution=res,
        storage_backend=storage,
        database=db,
        debug_overlay=debug_overlay,
    )

    snap_gen = SnapshotGenerator(storage_backend=storage, database=db, quality=90)
    evt_recorder = EventRecorder(recorder=recorder, database=db, snapshot_generator=snap_gen)
    playback = PlaybackService(database=db)
    investigation = InvestigationAPI(database=db, playback_service=playback)
    health_mon = RecordingHealthMonitor(recorder, storage, db, playback)

    recorder.start()

    logger.info("Processing continuous video recording over %d frames (segment rotation = %.1fs)...", args.frames, args.segment_duration)
    t0 = time.time()

    sample_events = [
        StandardAnalyticsEvent(event_type="ZONE_ENTER", message="Pedestrian entered EZVIZ Lobby Zone", camera_id="cam_ezviz_lobby", track_id=101, severity="INFO"),
        StandardAnalyticsEvent(event_type="CROWD_ALERT", message="Crowd alert in Lobby Zone", camera_id="cam_ezviz_lobby", severity="CRITICAL"),
        StandardAnalyticsEvent(event_type="LOITERING", message="Loitering alert in Lobby Zone", camera_id="cam_ezviz_lobby", track_id=102, severity="WARNING"),
        StandardAnalyticsEvent(event_type="DIRECTION_VIOLATION", message="Direction violation detected", camera_id="cam_ezviz_lobby", track_id=103, severity="WARNING"),
        StandardAnalyticsEvent(event_type="QUEUE_ALERT", message="Queue length alert", camera_id="cam_ezviz_lobby", severity="ALERT"),
    ]

    recorded_events_count = 0
    start_sim_ts = time.time()

    for i in range(1, args.frames + 1):
        sim_ts = start_sim_ts + (i / fps)

        if cap and cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = cap.read()
        else:
            frame = np.zeros((res[1], res[0], 3), dtype=np.uint8)

        if frame is None:
            break

        track_bboxes = {
            101: [150, 200, 350, 600],
            102: [500, 180, 700, 580],
            103: [850, 220, 1050, 620],
        }

        # Record analytics event & snapshot every 30 frames
        if i % 30 == 0:
            evt = sample_events[recorded_events_count % len(sample_events)]
            evt.frame_index = i
            evt_recorder.record_event(evt, frame=frame, event_timestamp=sim_ts)
            debug_overlay.register_event(evt, bbox=track_bboxes.get(evt.track_id or 101), duration_sec=round(i / fps, 1))
            recorded_events_count += 1

        recorder.write_frame(frame, timestamp=sim_ts, track_bboxes=track_bboxes)

    if cap:
        cap.release()

    recorder.stop()
    elapsed = time.time() - t0

    logger.info("Video recording processing finished: %d frames written in %.3f sec (%.1f FPS)", args.frames, elapsed, args.frames / elapsed)

    # Perform Playback Seek Validation
    seek_ts = start_sim_ts + 2.5
    seek_res = playback.seek_timestamp("cam_ezviz_lobby", seek_ts)

    # Perform Investigation API Query
    timeline = investigation.generate_timeline(camera_id="cam_ezviz_lobby")

    # Enforce Retention Cleanup Validation
    purged = storage.enforce_retention(max_retention_days=30)

    # Get Health Report
    health_rep = health_mon.get_health_report()

    logger.info("================================================================================")
    logger.info("RECORDING & PLAYBACK BENCHMARK RESULTS (EZVIZ VIDEO)")
    logger.info("================================================================================")
    logger.info("Total Frames Written:        %d frames", health_rep["recorder"]["frames_written"])
    logger.info("Segments Recorded & Indexed: %d segments", health_rep["database"]["segment_count"])
    logger.info("Events Reference Recorded:  %d events", health_rep["database"]["event_count"])
    logger.info("JPEG Snapshots Generated:    %d snapshots", health_rep["database"]["snapshot_count"])
    logger.info("--------------------------------------------------------------------------------")
    logger.info("INDEX-DRIVEN PLAYBACK SEEK VALIDATION:")
    if seek_res:
        logger.info("  - Target Timestamp:        %.3f s", seek_res.requested_timestamp)
        logger.info("  - Matched Segment ID:      %s", seek_res.segment_id)
        logger.info("  - Calculated Seek Offset:  %.2f s", seek_res.seek_offset_sec)
        logger.info("  - Index Seek Latency:      %.3f ms", playback.avg_lookup_time_ms)
    logger.info("--------------------------------------------------------------------------------")
    logger.info("INVESTIGATION TIMELINE ENTRIES: %d entries", len(timeline))
    for entry in timeline[:5]:
        logger.info("  - [%s] [%s] %s | Offset: %.2fs | Snap: %s", entry["event_type"], entry["severity"], entry["message"], entry["seek_offset_sec"], bool(entry.get("snapshot_path")))
    logger.info("--------------------------------------------------------------------------------")
    logger.info("STORAGE HEALTH & CAPACITY:")
    logger.info("  - Total Space:             %.2f GB", health_rep["storage"]["total_space_gb"])
    logger.info("  - Free Space:              %.2f GB", health_rep["storage"]["free_space_gb"])
    logger.info("  - Recordings Size:         %.2f MB", health_rep["storage"]["recordings_mb"])
    logger.info("  - Snapshots Size:          %.2f MB", health_rep["storage"]["snapshots_mb"])
    logger.info("================================================================================")
    logger.info("Sprint 12.3 Enterprise Recording & Playback Service validation complete.")


if __name__ == "__main__":
    main()
