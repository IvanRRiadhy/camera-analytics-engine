"""
BoT-SORT Tracking Validation and Visualization Tool.

Runs end-to-end tracking pipeline (VideoSource -> YOLO26m-Pose -> BoTSORTAdapter -> Pipeline -> TrackManager)
on real video sample and outputs an annotated video displaying:
    - Persistent Track ID, Bounding Box, and Confidence
    - Track Lifecycle State color coding:
        - GREEN: Confirmed Track
        - YELLOW: Tentative Track
        - RED: Lost Track
    - 17 COCO Pose Keypoint Skeleton
    - Color-coded Ground Point Marker (Green: Both Ankles, Yellow: Single Ankle, Red: Fallback)
    - Runtime Tracking Statistics (Active, Confirmed, Lost, Removed, New Tracks)

Usage::

    python -m camera_analytics.tools.validate_botsort_tracking
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
from camera_analytics.models import Camera
from camera_analytics.utils.visualizer import PoseVisualizer

logger = logging.getLogger("validate_botsort_tracking")


def setup_logging() -> None:
    """Configure logging format."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )


def validate_botsort_tracking(
    video_path: str,
    weights_path: str = "yolo26m-pose.pt",
    output_path: str = "camera_analytics/samples/output_botsort_tracking_validation.mp4",
    max_frames: int = 200,
    confidence_threshold: float = 0.45,
    device: str = "cuda",
) -> None:
    """Run BoT-SORT tracking validation on a video file and render visual overlays.

    Args:
        video_path: Path to input video file.
        weights_path: Path to YOLO weights file (.pt).
        output_path: Path for saving annotated output MP4.
        max_frames: Maximum frames to process (None for full video).
        confidence_threshold: Confidence threshold for detector.
        device: Target compute device ('cuda' or 'cpu').
    """
    setup_logging()

    logger.info("=" * 65)
    logger.info("Sprint 6B -- BoT-SORT Integration & Track Validation")
    logger.info("=" * 65)

    if not Path(video_path).exists():
        logger.error("Input video file not found: %s", video_path)
        return

    # 1. Initialize Adapters
    detector = YOLOPoseAdapter(
        confidence_threshold=confidence_threshold,
        iou_threshold=0.45,
    )
    detector.load(weights_path, device=device)

    tracker = BoTSORTAdapter(track_high_thresh=0.5, match_thresh=0.8)
    tracker.initialize()

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

    # 3. Setup Framework Pipeline & TrackManager
    camera = Camera("cam_val", "Validation Camera", video_path)
    camera.update_resolution(width, height, fps)
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

    # 4. Prepare VideoWriter & Visualizer
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    visualizer = PoseVisualizer(keypoint_threshold=0.5)

    logger.info("Rendering annotated validation video to: %s", output_path)
    logger.info("-" * 65)

    frame_count = 0
    start_time = time.perf_counter()

    try:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret or frame is None:
                break

            frame_count += 1
            f_start = time.perf_counter()

            # Step 1: Detector inference
            det_res = detector.detect(frame)

            # Step 2: Tracker data association
            trk_res = tracker.track(frame, det_res)

            # Step 3: Pipeline Execution & TrackManager update
            pipeline.process(frame, trk_res.results)

            f_elapsed = time.perf_counter() - f_start
            current_fps = 1.0 / max(f_elapsed, 0.0001)

            # Step 4: Get active & lost tracks from TrackManager
            runtime = pipeline.runtime
            active_tracks = runtime.track_manager.get_active() if runtime else []
            confirmed_tracks = runtime.track_manager.get_confirmed() if runtime else []
            lost_tracks = runtime.track_manager.get_lost() if runtime else []

            # Step 5: Render Visual Overlays
            annotated_frame = visualizer.draw_tracks(
                frame=frame,
                tracks=active_tracks,
                frame_id=frame_count,
                fps=current_fps,
                device=f"{detector.device.upper()} ({detector.name})",
                model_name="YOLO26m-Pose",
                tracker_name=tracker.name.upper(),
            )

            # Write annotated frame
            writer.write(annotated_frame)

            if frame_count % 30 == 0:
                logger.info(
                    "Processed %d frames (FPS: %.1f, Active Tracks: %d [Conf: %d, Lost: %d])",
                    frame_count,
                    current_fps,
                    len(active_tracks),
                    len(confirmed_tracks),
                    len(lost_tracks),
                )

            if max_frames is not None and frame_count >= max_frames:
                logger.info("Reached maximum frame limit (%d)", max_frames)
                break

    finally:
        total_time = time.perf_counter() - start_time
        avg_fps = frame_count / max(total_time, 0.0001)

        cap.release()
        writer.release()
        pipeline.stop()
        detector.release()
        tracker.reset()

    # Runtime Statistics Summary Report
    runtime_tm = pipeline.runtime.track_manager if pipeline.runtime else None
    total_created = runtime_tm.total_created if runtime_tm else 0
    total_deleted = runtime_tm.total_deleted if runtime_tm else 0

    logger.info("-" * 65)
    logger.info("VALIDATION SUMMARY REPORT")
    logger.info("-" * 65)
    logger.info("Total Frames Processed:    %d", frame_count)
    logger.info("Total Time Elapsed:        %.2f seconds", total_time)
    logger.info("Average Speed:             %.1f FPS", avg_fps)
    logger.info("Runtime Track Statistics:")
    logger.info("  - New Tracks Created:    %d", total_created)
    logger.info("  - Total Tracks Removed:  %d", total_deleted)
    logger.info("  - Final Active Tracks:   %d", len(active_tracks))
    logger.info("  - Final Confirmed Tracks:%d", len(confirmed_tracks))
    logger.info("Rendered Output Saved to:  %s", output_path)
    logger.info("Sprint 6B Validation complete.")


if __name__ == "__main__":
    sample_paths = [
        "camera_analytics/samples/Screen_Recording_20260622_113428_EZVIZ.mp4",
        "AI/data/Screen_Recording_20260622_113428_EZVIZ.mp4",
    ]
    target_video = next((p for p in sample_paths if Path(p).exists()), sample_paths[0])

    validate_botsort_tracking(
        video_path=target_video,
        weights_path="yolo26m-pose.pt",
        output_path="camera_analytics/samples/output_botsort_tracking_validation.mp4",
        max_frames=200,
        device="cuda",
    )
