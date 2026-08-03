"""
Live RTSP Performance & Stability Validation Tool.

Executes real-time live camera validation using RTSPSource -> YOLO26m-Pose -> BoTSORT -> Pipeline -> TrackManager.
Collects resource usage metrics (CPU, RAM, GPU, VRAM), measures frame latencies, renders structured
live performance overlays, and generates the Camera Validation Benchmark Report upon shutdown.

Usage::

    python -m camera_analytics.tools.validate_live_rtsp --rtsp-url "rtsp://username:password@ip:port/stream"
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import Optional

import cv2

from camera_analytics.adapters.detection.yolo_pose_adapter import YOLOPoseAdapter
from camera_analytics.adapters.tracking.botsort_adapter import BoTSORTAdapter
from camera_analytics.core import Config, EventBus, Pipeline
from camera_analytics.models import Camera
from camera_analytics.sources.rtsp_source import RTSPSource
from camera_analytics.utils.resource_monitor import BenchmarkCollector
from camera_analytics.utils.visualizer import PoseVisualizer

logger = logging.getLogger("validate_live_rtsp")


def setup_logging() -> None:
    """Configure logging format."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )


def validate_live_rtsp(
    rtsp_url: str,
    weights_path: str = "yolo26m-pose.pt",
    output_path: Optional[str] = "camera_analytics/samples/output_live_rtsp_validation.mp4",
    max_frames: Optional[int] = 300,
    confidence_threshold: float = 0.45,
    device: str = "cuda",
    reconnect_delay: float = 3.0,
    buffer_size: int = 1,
    show_preview: bool = False,
) -> None:
    """Run live RTSP performance validation loop and generate benchmark report.

    Args:
        rtsp_url: RTSP connection URL (e.g. 'rtsp://user:pass@ip:port/stream').
        weights_path: Path to YOLO weights file (.pt).
        output_path: Optional output video path to record live validation.
        max_frames: Max frames to process (None for continuous long-run test).
        confidence_threshold: Detector confidence threshold.
        device: Target compute device ('cuda' or 'cpu').
        reconnect_delay: Delay in seconds between reconnect retries.
        buffer_size: RTSP stream buffer size.
        show_preview: Whether to display live preview window.
    """
    setup_logging()

    logger.info("=" * 70)
    logger.info("Sprint 6C -- Live Camera Performance & Stability Validation")
    logger.info("=" * 70)

    # 1. Initialize Adapters & Benchmark Collector
    collector = BenchmarkCollector(camera_name=f"RTSP Live Camera ({rtsp_url})")

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
    logger.info("YOLOPoseAdapter running on device: %s", active_device)

    tracker = BoTSORTAdapter(track_high_thresh=0.5, match_thresh=0.8)
    tracker.initialize()

    # 2. Initialize RTSPSource
    source = RTSPSource(
        rtsp_url=rtsp_url,
        reconnect_delay=reconnect_delay,
        buffer_size=buffer_size,
    )
    source.open()

    # 3. Setup Framework Pipeline & TrackManager
    camera = Camera("cam_live_rtsp", "Live RTSP Camera", rtsp_url)
    camera.update_resolution(1920, 1080, 30.0)
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

    # 4. Setup VideoWriter & Visualizer
    writer: Optional[cv2.VideoWriter] = None
    visualizer = PoseVisualizer(keypoint_threshold=0.5)

    frame_count = 0
    start_time = time.monotonic()
    logger.info("Starting Live RTSP Performance Validation Loop...")
    logger.info("-" * 70)

    try:
        while source.is_open:
            t0 = time.monotonic()

            # Step 1: Capture Frame from RTSPSource
            packet = source.read()
            if packet is None or packet.image is None:
                time.sleep(0.01)
                continue

            frame = packet.image
            h, w = frame.shape[:2]
            collector.input_resolution = (w, h)
            collector.processing_resolution = (w, h)

            if writer is None and output_path:
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                writer = cv2.VideoWriter(output_path, fourcc, source.metadata.fps, (w, h))

            t1 = time.monotonic()
            capture_ms = (t1 - t0) * 1000.0

            # Step 2: Detect via YOLO26m-Pose
            det_res = detector.detect(frame)
            t2 = time.monotonic()
            detection_ms = (t2 - t1) * 1000.0

            # Step 3: Track via BoTSORT
            trk_res = tracker.track(frame, det_res)
            t3 = time.monotonic()
            tracking_ms = (t3 - t2) * 1000.0

            # Step 4: Pipeline Execution & TrackManager update
            pipeline.process(frame, trk_res.results)

            # Step 5: Get active tracks & update collector
            runtime = pipeline.runtime
            active_tracks = runtime.track_manager.get_active() if runtime else []

            # Step 6: Render Visual Overlays & Live Benchmark Panel
            annotated_frame = visualizer.draw_tracks(
                frame=frame,
                tracks=active_tracks,
                frame_id=frame_count + 1,
                fps=0.0,
                device=f"{active_device} ({detector.name})",
                model_name="YOLO26m-Pose",
                tracker_name=tracker.name.upper(),
                benchmark_collector=collector,
            )
            t4 = time.monotonic()
            rendering_ms = (t4 - t3) * 1000.0

            frame_count += 1
            sample = collector.record_frame(
                frame_id=frame_count,
                capture_ms=capture_ms,
                detection_ms=detection_ms,
                tracking_ms=tracking_ms,
                rendering_ms=rendering_ms,
            )

            collector.reconnect_count = source.reconnect_count
            collector.dropped_frames = source.dropped_frames

            # Write frame if recording
            if writer:
                writer.write(annotated_frame)

            # Performance Warnings
            if sample.total_latency_ms > 100.0:
                logger.warning("Slow Frame Warning: Total latency %.1fms on Frame #%d",
                               sample.total_latency_ms, frame_count)
            if sample.fps < 10.0 and frame_count > 30:
                logger.warning("Low FPS Warning: Processing speed dropped to %.1f FPS", sample.fps)

            # Optional live window preview
            if show_preview:
                try:
                    cv2.imshow("Live RTSP Performance & Stability Validation", annotated_frame)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        logger.info("Live preview stopped by user keypress 'q'")
                        break
                except Exception:
                    show_preview = False

            if frame_count % 50 == 0:
                logger.info(
                    "FRAME #%d | Display FPS: %.1f | Latency: %.1fms | Active Tracks: %d | Reconnects: %d | Drops: %d",
                    frame_count,
                    sample.fps,
                    sample.total_latency_ms,
                    len(active_tracks),
                    source.reconnect_count,
                    source.dropped_frames,
                )

            if max_frames is not None and frame_count >= max_frames:
                logger.info("Reached maximum requested frames limit (%d)", max_frames)
                break

    except KeyboardInterrupt:
        logger.info("Live validation loop interrupted by user (Ctrl+C).")
    finally:
        source.release()
        if writer:
            writer.release()
        if show_preview:
            try:
                cv2.destroyAllWindows()
            except Exception:
                pass
        pipeline.stop()
        detector.release()
        tracker.reset()

    # Generate and print formal Camera Validation Benchmark Report
    logger.info("\n" + collector.generate_report())
    logger.info("Sprint 6C Live Camera Validation complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Live RTSP Performance & Stability Validation Tool")
    parser.add_argument(
        "--rtsp-url",
        type=str,
        default="rtsp://admin:Admin1234@192.168.1.64/Streaming/channels/2",
        help="RTSP camera stream URL or video file path for testing",
    )
    parser.add_argument("--max-frames", type=int, default=250, help="Maximum frames to run (None for long test)")
    parser.add_argument("--device", type=str, default="cuda", help="Compute device ('cuda' or 'cpu')")

    args = parser.parse_args()

    validate_live_rtsp(
        rtsp_url=args.rtsp_url,
        weights_path="yolo26m-pose.pt",
        output_path="camera_analytics/samples/output_live_rtsp_validation.mp4",
        max_frames=args.max_frames,
        device=args.device,
    )
