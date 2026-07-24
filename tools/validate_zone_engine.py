"""
Zone Engine Validation and Visualization Tool.

Runs full end-to-end pipeline (VideoSource -> YOLO26m-Pose -> BoTSORT -> TrackManager -> ZoneEngine)
on real video sample and outputs an annotated video displaying:
    - Translucent Polygon Zones with border outline & zone name labels
    - Track ID, Track State ([CONFIRMED] / [TENTATIVE]), and Current Zone Membership
    - 17 COCO Pose Keypoint Skeleton
    - Color-coded Ground Point Markers
    - Runtime Zone Event Counters (ENTER, EXIT, STAY)

Usage::

    python -m camera_analytics.tools.validate_zone_engine
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

import cv2

from camera_analytics.adapters.detection.yolo_pose_adapter import YOLOPoseAdapter
from camera_analytics.adapters.tracking.botsort_adapter import BoTSORTAdapter
from camera_analytics.core import Config, EventBus, Pipeline
from camera_analytics.core.zone_engine import ZoneEngine, ZoneEventType
from camera_analytics.models import Camera, Point, Zone, ZoneType
from camera_analytics.utils.visualizer import PoseVisualizer

logger = logging.getLogger("validate_zone_engine")


def setup_logging() -> None:
    """Configure logging format."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )


def validate_zone_engine(
    video_path: str,
    weights_path: str = "yolo26m-pose.pt",
    output_path: str = "camera_analytics/samples/output_zone_engine_validation.mp4",
    max_frames: int = 200,
    confidence_threshold: float = 0.45,
    device: str = "cuda",
) -> None:
    """Run Zone Engine validation on a video stream and render visual overlays.

    Args:
        video_path: Path to input video file.
        weights_path: Path to YOLO weights file (.pt).
        output_path: Output path for rendered MP4.
        max_frames: Maximum frames to process (None for full video).
        confidence_threshold: Detector confidence threshold.
        device: Compute device ('cuda' or 'cpu').
    """
    setup_logging()

    logger.info("=" * 65)
    logger.info("Sprint 7 -- Zone Engine Spatial Validation & Event Visualization")
    logger.info("=" * 65)

    if not Path(video_path).exists():
        logger.error("Input video file not found: %s", video_path)
        return

    # 1. Initialize Adapters & ZoneEngine
    detector = YOLOPoseAdapter(
        confidence_threshold=confidence_threshold,
        iou_threshold=0.45,
    )
    detector.load(weights_path, device=device)

    tracker = BoTSORTAdapter(track_high_thresh=0.5, match_thresh=0.8)
    tracker.initialize()

    zone_engine = ZoneEngine()

    # 2. Open Video Stream via OpenCV
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        logger.error("Could not open video file: %s", video_path)
        detector.release()
        tracker.reset()
        return

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    logger.info("Input Video: %s (%dx%d @ %.1f FPS, Total Frames: %d)",
                video_path, width, height, fps, total_frames)

    # 3. Setup Polygon Zones
    zone_critical = Zone(
        zone_id="critical",
        name="Critical Area",
        zone_type=ZoneType.REGION,
        points=[
            Point(380, 360),
            Point(830, 250),
            Point(800, 360),
            Point(470, 470),
        ],
        color=(255, 0, 255),
    )

    zone_lobby = Zone(
        zone_id="lobby_main",
        name="Main Entrance",
        zone_type=ZoneType.REGION,
        points=[
            Point(560, 860),
            Point(1100, 720),
            Point(1500, 1070),
            Point(500, 1070),
        ],
        color=(0, 220, 0),
    )

    zone_restricted = Zone(
        zone_id="restricted_room",
        name="Restricted Room",
        zone_type=ZoneType.REGION,
        points=[
            Point(960, 380),
            Point(1200, 80),
            Point(1900, 620),
            Point(1800, 990),
        ],
        color=(0, 0, 255),
    )

    zones = [zone_critical, zone_lobby, zone_restricted]

    # 4. Setup Framework Pipeline & TrackManager
    camera = Camera("cam_zone_val", "Zone Validation Camera", video_path)
    camera.update_resolution(width, height, fps)
    for z in zones:
        camera.add_zone(z)
    camera.set_online()

    pipeline_cfg = Config.from_dict({
        "pipeline": {"process_every_n": 1},
        "track_manager": {
            "max_history_length": 150,
            "confirm_after_n": 3,
            "max_lost_age": 30,
            "max_archived": 500,
        },
    })
    event_bus = EventBus()
    pipeline = Pipeline(pipeline_cfg, camera, event_bus)
    pipeline.start()

    # 5. Prepare VideoWriter & Visualizer
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    visualizer = PoseVisualizer(keypoint_threshold=0.5)

    logger.info("Rendering annotated validation video to: %s", output_path)
    logger.info("-" * 65)

    frame_count = 0
    total_enter_events = 0
    total_exit_events = 0
    start_time = time.perf_counter()

    try:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret or frame is None:
                break

            frame_count += 1
            timestamp = (frame_count - 1) / fps
            f_start = time.perf_counter()

            # Step 1: Detect
            det_res = detector.detect(frame)

            # Step 2: Track
            trk_res = tracker.track(frame, det_res)

            # Step 3: Pipeline Execution & TrackManager update
            pipeline.process(frame, trk_res.results)

            # Step 4: Get active tracks from TrackManager
            runtime = pipeline.runtime
            active_tracks = runtime.track_manager.get_active() if runtime else []

            # Step 5: Execute Zone Engine spatial processing
            zone_res = zone_engine.process(
                tracks=active_tracks,
                zones=zones,
                frame_index=frame_count,
                timestamp=timestamp,
            )

            # Count emitted events for validation report
            for evt in zone_res.events:
                if evt.event_type == ZoneEventType.ENTER:
                    total_enter_events += 1
                    logger.info("FRAME %d | ZoneEvent [ENTER]: Track #%d -> '%s'",
                                frame_count, evt.track_id, evt.zone_name)
                elif evt.event_type == ZoneEventType.EXIT:
                    total_exit_events += 1
                    logger.info("FRAME %d | ZoneEvent [EXIT]: Track #%d <- '%s'",
                                frame_count, evt.track_id, evt.zone_name)

            f_elapsed = time.perf_counter() - f_start
            current_fps = 1.0 / max(f_elapsed, 0.0001)

            # Step 6: Render Visual Overlays (Polygon Zones + Tracks + Zone membership)
            annotated_frame = visualizer.draw_tracks(
                frame=frame,
                tracks=active_tracks,
                zones=zones,
                track_zone_states=zone_res.track_states,
                frame_id=frame_count,
                fps=current_fps,
                device=f"{detector.device.upper()} ({detector.name})",
                model_name="YOLO26m-Pose",
                tracker_name=tracker.name.upper(),
            )

            writer.write(annotated_frame)

            if frame_count % 30 == 0:
                logger.info("Processed %d frames (FPS: %.1f, Active Tracks: %d, Enter Events: %d, Exit Events: %d)",
                            frame_count, current_fps, len(active_tracks), total_enter_events, total_exit_events)

            if max_frames is not None and frame_count >= max_frames:
                logger.info("Reached maximum requested frames (%d)", max_frames)
                break

    finally:
        total_time = time.perf_counter() - start_time
        avg_fps = frame_count / max(total_time, 0.0001)

        cap.release()
        writer.release()
        pipeline.stop()
        detector.release()
        tracker.reset()
        zone_engine.reset()

    logger.info("-" * 65)
    logger.info("ZONE ENGINE VALIDATION SUMMARY REPORT")
    logger.info("-" * 65)
    logger.info("Total Frames Processed:    %d", frame_count)
    logger.info("Total Time Elapsed:        %.2f seconds", total_time)
    logger.info("Average Processing Speed:  %.1f FPS", avg_fps)
    logger.info("Zone Event Summary:")
    logger.info("  - Total ENTER Events:    %d (Single-fire per entry)", total_enter_events)
    logger.info("  - Total EXIT Events:     %d (Single-fire per exit)", total_exit_events)
    logger.info("Rendered Output Saved to:  %s", output_path)
    logger.info("Sprint 7 Zone Engine validation complete.")


if __name__ == "__main__":
    sample_paths = [
        "camera_analytics/samples/Screen_Recording_20260622_113428_EZVIZ.mp4",
        "AI/data/Screen_Recording_20260622_113428_EZVIZ.mp4",
    ]
    target_video = next((p for p in sample_paths if Path(p).exists()), sample_paths[0])

    validate_zone_engine(
        video_path=target_video,
        weights_path="yolo26m-pose.pt",
        output_path="camera_analytics/samples/output_zone_engine_validation.mp4",
        max_frames=None,
        device="cuda",
    )
