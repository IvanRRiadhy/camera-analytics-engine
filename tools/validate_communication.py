"""
Event Communication Layer Validation Tool.

Executes real inference pipeline (YOLO26m-Pose -> BoTSORT -> Pipeline -> ZoneEngine -> Analytics SDK -> Communication Layer).

Validates:
    - Analytics Event emission via non-blocking PublishQueue.
    - Background worker thread event processing.
    - Event writing to JSON Lines (.jsonl) log file (`camera_analytics/logs/events_validation.jsonl`).
    - MQTT Publisher event broadcasting (with safe fallback if broker offline).
    - Communication Runtime Metrics summary report.

Usage::

    python -m camera_analytics.tools.validate_communication
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
from camera_analytics.communication import (
    CommunicationManager,
    LogPublisher,
    MQTTPublisher,
    StandardAnalyticsEvent,
)
from camera_analytics.core import Config, EventBus, Pipeline
from camera_analytics.core.zone_engine import ZoneEngine
from camera_analytics.models import Camera, Point, Zone, ZoneType
from camera_analytics.sdk import (
    AnalyticsContext,
    AnalyticsManager,
    AnalyticsRegistry,
    DummyAnalytics,
)
from camera_analytics.sources.video_source import VideoSource
from camera_analytics.utils.visualizer import PoseVisualizer

logger = logging.getLogger("validate_communication")


def setup_logging() -> None:
    """Configure logging format."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )


def validate_communication(
    video_path: str = "camera_analytics/samples/Screen_Recording_20260622_113428_EZVIZ.mp4",
    weights_path: str = "yolo26m-pose.pt",
    output_path: str = "camera_analytics/samples/output_communication_validation.mp4",
    log_output_path: str = "camera_analytics/logs/events_validation.jsonl",
    max_frames: Optional[int] = 200,
    confidence_threshold: float = 0.45,
    device: str = "cuda",
) -> None:
    """Run full pipeline validation integrated with Event Communication Layer."""
    setup_logging()

    logger.info("=" * 70)
    logger.info("Sprint 8A -- Event Communication Layer Validation")
    logger.info("=" * 70)

    # 1. Initialize Communication Layer & Publishers
    comm_manager = CommunicationManager.get_instance(queue_size=10000)

    log_pub = LogPublisher(
        name="validation_log_publisher",
        log_dir=str(Path(log_output_path).parent),
        filename_pattern=Path(log_output_path).name,
        rotate_daily=False,
    )
    mqtt_pub = MQTTPublisher(
        name="validation_mqtt_publisher",
        broker="localhost",
        port=1883,
        topic="camera/{camera_id}/analytics/events",
    )

    comm_manager.publisher_manager.register_publisher(log_pub)
    comm_manager.publisher_manager.register_publisher(mqtt_pub)

    comm_manager.initialize({})
    comm_manager.start()

    # 2. Initialize AI Adapters
    detector = YOLOPoseAdapter(
        confidence_threshold=confidence_threshold,
        iou_threshold=0.45,
    )
    detector.load(weights_path, device=device)

    tracker = BoTSORTAdapter(track_high_thresh=0.5, match_thresh=0.8)
    tracker.initialize()

    # 3. Setup Polygon Zones & Zone Engine
    zone_main = Zone(
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
    zones = [zone_main]
    zone_engine = ZoneEngine()

    # 4. Setup Framework Core Pipeline & Camera
    camera = Camera("cam_comm_val", "Main Lobby Camera", video_path)
    for z in zones:
        camera.add_zone(z)

    pipeline_cfg = Config.from_dict({
        "pipeline": {"process_every_n": 1},
        "track_manager": {
            "max_history_length": 150,
            "confirm_after_n": 3,
            "max_lost_age": 30,
        },
    })
    event_bus = EventBus()
    pipeline = Pipeline(pipeline_cfg, camera, event_bus)
    pipeline.start()

    # 5. Setup Analytics Engine & Register DummyAnalytics
    analytics_manager = AnalyticsManager()
    dummy_plugin = AnalyticsRegistry.create("dummy_analytics")
    analytics_manager.register_module(dummy_plugin)

    init_context = AnalyticsContext(
        frame_context=None,
        runtime_state=pipeline.runtime,
        track_manager=pipeline.runtime.track_manager if pipeline.runtime else None,
        zones=zones,
    )
    analytics_manager.initialize(init_context)
    analytics_manager.start()

    # 6. Open Video Source & VideoWriter
    source = VideoSource(video_path)
    source.open()
    w, h = source.metadata.resolution
    fps = source.metadata.fps

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(output_path, fourcc, fps, (w, h))

    visualizer = PoseVisualizer(keypoint_threshold=0.5)

    frame_count = 0
    start_time = time.monotonic()

    track_history_ids: set[int] = set()

    logger.info("Processing frames with Event Communication Layer...")
    logger.info("-" * 70)

    try:
        while source.is_open:
            packet = source.read()
            if packet is None or packet.image is None:
                break

            frame_count += 1
            frame = packet.image

            # AI Inference & Tracking
            det_res = detector.detect(frame)
            trk_res = tracker.track(frame, det_res)

            # Core Pipeline & TrackManager processing
            frame_ctx = pipeline.process(frame, trk_res.results)

            runtime = pipeline.runtime
            active_tracks = runtime.track_manager.get_active() if runtime else []

            newly_created = [t for t in active_tracks if t.track_id not in track_history_ids]
            for t in newly_created:
                track_history_ids.add(t.track_id)

            # Zone Engine Spatial Evaluation
            zone_result = zone_engine.process(
                tracks=active_tracks,
                zones=zones,
                frame_index=frame_count,
                timestamp=packet.timestamp,
            )

            # Analytics SDK Update Iteration
            analytics_ctx = AnalyticsContext(
                frame_context=frame_ctx,
                runtime_state=runtime,
                track_manager=runtime.track_manager if runtime else None,
                active_tracks=active_tracks,
                zones=zones,
                zone_result=zone_result,
                frame_index=frame_count,
                timestamp=packet.timestamp,
            )

            aggregated_res = analytics_manager.process(
                context=analytics_ctx,
                tracks_created=newly_created,
            )

            # Convert Analytics Events into StandardAnalyticsEvent payloads and enqueue into CommunicationManager
            for evt in aggregated_res.all_events:
                std_evt = StandardAnalyticsEvent(
                    camera_id=camera.camera_id,
                    camera_name=camera.name,
                    analytics_module=evt.module_name,
                    event_type=evt.event_type.name,
                    message=evt.message,
                    track_id=evt.track_id,
                    zone_id=evt.zone_id,
                    frame_index=evt.frame_index,
                    payload=evt.data,
                )
                comm_manager.enqueue(std_evt)

            # Visualization Rendering
            annotated_frame = visualizer.draw_tracks(
                frame=frame,
                tracks=active_tracks,
                zones=zones,
                track_zone_states=zone_result.track_states,
                frame_id=frame_count,
                fps=fps,
                device=f"CUDA ({detector.name})",
                model_name="YOLO26m-Pose + Comm Layer",
                tracker_name=tracker.name.upper(),
            )

            writer.write(annotated_frame)

            if frame_count % 50 == 0:
                metrics = comm_manager.get_metrics()
                logger.info(
                    "FRAME %d | Enqueued: %d | Published: %d | Queue Size: %d | Dropped: %d",
                    frame_count,
                    metrics.total_events,
                    metrics.published_events,
                    metrics.queue_size,
                    metrics.dropped_events,
                )

            if max_frames is not None and frame_count >= max_frames:
                logger.info("Reached maximum requested frames limit (%d)", max_frames)
                break

    finally:
        source.release()
        writer.release()
        analytics_manager.stop()
        analytics_manager.dispose()
        comm_manager.stop()
        comm_manager.dispose()
        pipeline.stop()
        detector.release()
        tracker.reset()
        zone_engine.reset()

    elapsed = time.monotonic() - start_time
    avg_fps = frame_count / max(elapsed, 0.001)
    metrics = comm_manager.get_metrics()

    logger.info("-" * 70)
    logger.info("EVENT COMMUNICATION LAYER SUMMARY REPORT")
    logger.info("-" * 70)
    logger.info("Total Frames Processed:    %d", frame_count)
    logger.info("Total Time Elapsed:        %.2f seconds", elapsed)
    logger.info("Average Processing Speed:  %.1f FPS", avg_fps)
    logger.info("Total Events Enqueued:     %d", metrics.total_events)
    logger.info("Total Events Published:    %d", metrics.published_events)
    logger.info("Failed Event Publishes:    %d", metrics.failed_events)
    logger.info("Dropped Events (Queue):    %d", metrics.dropped_events)
    logger.info("Average Publish Time:      %.2f ms", metrics.avg_publish_time_ms)
    logger.info("JSON Lines Log Saved to:   %s", log_output_path)
    logger.info("Rendered Output Saved to:  %s", output_path)
    logger.info("Sprint 8A Event Communication Layer validation complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Event Communication Layer Validation Tool")
    parser.add_argument(
        "--video",
        type=str,
        default="camera_analytics/samples/Screen_Recording_20260622_113428_EZVIZ.mp4",
        help="Path to input video file",
    )
    parser.add_argument("--max-frames", type=int, default=200, help="Max frames to process")
    args = parser.parse_args()

    validate_communication(video_path=args.video, max_frames=args.max_frames)
