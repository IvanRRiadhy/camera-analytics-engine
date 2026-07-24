"""
Validation script for YOLO26m-Pose inference and visual overlay mapping.

Executes real video inference using VideoSource -> Runner -> YOLOPoseAdapter,
applies visual overlays via PoseVisualizer, and outputs a rendered validation video
to confirm the accuracy of bounding boxes, 17 COCO keypoints, and color-coded ground points.

Usage::

    python -m camera_analytics.tools.validate_yolo_pose
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

import cv2

from camera_analytics.adapters.detection.yolo_pose_adapter import YOLOPoseAdapter
from camera_analytics.models.detection import Detection
from camera_analytics.utils.visualizer import PoseVisualizer

logger = logging.getLogger("validate_yolo_pose")


def setup_logging() -> None:
    """Configure logging format."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )


def validate_yolo_pose(
    video_path: str,
    weights_path: str = "yolo26m-pose.pt",
    output_path: str = "camera_analytics/samples/output_yolo_pose_validation.mp4",
    max_frames: int = 150,
    confidence_threshold: float = 0.45,
    device: str = "cuda",
    show_preview: bool = False,
) -> None:
    """Run YOLO-Pose validation on a video file and render output video with visual overlays.

    Args:
        video_path: Path to input video file.
        weights_path: Path to YOLO-Pose weights file (.pt).
        output_path: Path to save rendered validation video.
        max_frames: Maximum number of frames to process.
        confidence_threshold: Detector confidence threshold.
        device: Target compute device ('cuda' or 'cpu').
        show_preview: Whether to display a live window preview (if GUI supported).
    """
    setup_logging()

    logger.info("=" * 65)
    logger.info("Sprint 6A -- YOLO26m-Pose Inference Validation & Visualization")
    logger.info("=" * 65)

    if not Path(video_path).exists():
        logger.error("Input video file not found: %s", video_path)
        return

    # 1. Initialize YOLOPoseAdapter
    detector = YOLOPoseAdapter(
        confidence_threshold=confidence_threshold,
        iou_threshold=0.45,
    )

    try:
        detector.load(weights_path, device=device)
    except Exception as exc:
        logger.error("Failed to load YOLO model: %s", exc)
        return

    active_device = detector.device.upper()
    logger.info("YOLOPoseAdapter active on device: %s", active_device)

    # 2. Open Video Stream via OpenCV
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        logger.error("Could not open video file: %s", video_path)
        detector.release()
        return

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_video_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    logger.info("Input Video: %s (%dx%d @ %.1f FPS, Total Frames: %d)",
                video_path, width, height, fps, total_video_frames)

    # 3. Create VideoWriter & PoseVisualizer
    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    video_writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    visualizer = PoseVisualizer(keypoint_threshold=0.5)

    logger.info("Rendering annotated validation video to: %s", output_path)
    logger.info("-" * 65)

    # Statistics counters
    total_frames_processed = 0
    total_detections_count = 0
    ground_both_count = 0
    ground_single_count = 0
    ground_fallback_count = 0

    start_time = time.perf_counter()

    try:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret or frame is None:
                break

            total_frames_processed += 1

            # Run detection inferencing
            frame_start = time.perf_counter()
            det_result = detector.detect(frame)
            frame_elapsed_sec = time.perf_counter() - frame_start
            current_fps = 1.0 / max(frame_elapsed_sec, 0.0001)

            detections: list[Detection] = list(det_result.detections)
            total_detections_count += len(detections)

            # Analyze ground point statistics for validation summary
            for det in detections:
                if det.keypoints is not None:
                    l_vis = det.keypoints.left_ankle is not None and det.keypoints.left_ankle.confidence >= 0.5
                    r_vis = det.keypoints.right_ankle is not None and det.keypoints.right_ankle.confidence >= 0.5
                    if l_vis and r_vis:
                        ground_both_count += 1
                    elif l_vis or r_vis:
                        ground_single_count += 1
                    else:
                        ground_fallback_count += 1
                else:
                    ground_fallback_count += 1

            # Render visual overlays
            annotated_frame = visualizer.draw_frame(
                frame=frame,
                detections=detections,
                frame_id=total_frames_processed,
                fps=current_fps,
                device=f"{active_device} ({detector.name})",
                model_name="YOLO26m-Pose",
            )

            # Write annotated frame to output video file
            video_writer.write(annotated_frame)

            # Optional live window preview
            if show_preview:
                try:
                    cv2.imshow("YOLO26m-Pose Validation", annotated_frame)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        logger.info("Preview stopped by user keypress 'q'")
                        break
                except Exception:
                    show_preview = False

            if total_frames_processed % 30 == 0:
                logger.info("Processed %d frames (FPS: %.1f, Detections: %d)",
                            total_frames_processed, current_fps, len(detections))

            if max_frames is not None and total_frames_processed >= max_frames:
                logger.info("Reached maximum requested frames limit (%d)", max_frames)
                break

    finally:
        total_time_sec = time.perf_counter() - start_time
        avg_fps = total_frames_processed / max(total_time_sec, 0.0001)

        cap.release()
        video_writer.release()
        if show_preview:
            try:
                cv2.destroyAllWindows()
            except Exception:
                pass
        detector.release()

    # Output Summary Report
    logger.info("-" * 65)
    logger.info("VALIDATION SUMMARY REPORT")
    logger.info("-" * 65)
    logger.info("Total Frames Processed:    %d", total_frames_processed)
    logger.info("Total Time Elapsed:        %.2f seconds", total_time_sec)
    logger.info("Average Processing Speed:  %.1f FPS", avg_fps)
    logger.info("Total Person Detections:   %d", total_detections_count)
    logger.info("Ground Point Breakdown:")
    logger.info("  [GREEN] Both Ankles:    %d (%.1f%%)",
                ground_both_count,
                (ground_both_count / max(total_detections_count, 1)) * 100)
    logger.info("  [YELLOW] Single Ankle:  %d (%.1f%%)",
                ground_single_count,
                (ground_single_count / max(total_detections_count, 1)) * 100)
    logger.info("  [RED] BBox Fallback:    %d (%.1f%%)",
                ground_fallback_count,
                (ground_fallback_count / max(total_detections_count, 1)) * 100)
    logger.info("-" * 65)
    logger.info("Rendered Output Saved to:  %s", output_path)
    logger.info("Sprint 6A Validation complete.")


if __name__ == "__main__":
    sample_video = "camera_analytics/samples/Screen_Recording_20260622_113428_EZVIZ.mp4"
    weights_file = "yolo26m-pose.pt"

    validate_yolo_pose(
        video_path=sample_video,
        weights_path=weights_file,
        output_path="camera_analytics/samples/output_yolo_pose_validation.mp4",
        max_frames=150,
        device="cuda",
    )
