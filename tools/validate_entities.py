"""
Domain Entity Model & Payload SDK Validation Tool.

Executes real inference pipeline (YOLO26m-Pose -> BoTSORT -> Pipeline -> ZoneEngine -> EntityFactory -> Payload SDK -> EntitySerializer -> Communication Layer).

Validates:
    - Strongly typed Entity manufacturing via EntityFactory (TrackEntity, CameraEntity, ZoneEntity, FrameEntity).
    - AnalyticsPayload SDK filling by Analytics Modules without manual JSON construction.
    - EntitySerializer transforming Entities & AnalyticsPayload into StandardAnalyticsEvent payloads.
    - Writing serialized events to JSON Lines (.jsonl) log file (`camera_analytics/logs/entities_validation.jsonl`).

Usage::

    python -m camera_analytics.tools.validate_entities
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
)
from camera_analytics.core import Config, EventBus, Pipeline
from camera_analytics.core.zone_engine import ZoneEngine
from camera_analytics.entities import (
    AnalyticsPayload,
    EntityFactory,
    EntitySerializer,
    ZoneState,
)
from camera_analytics.models import Camera, Point, Zone, ZoneType
from camera_analytics.sdk import (
    AnalyticsContext,
    AnalyticsManager,
    AnalyticsRegistry,
    DummyAnalytics,
)
from camera_analytics.sources.video_source import VideoSource
from camera_analytics.utils.visualizer import PoseVisualizer

logger = logging.getLogger("validate_entities")


def setup_logging() -> None:
    """Configure logging format."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )


def validate_entities(
    video_path: str = "camera_analytics/samples/Screen_Recording_20260622_113428_EZVIZ.mp4",
    weights_path: str = "yolo26m-pose.pt",
    output_path: str = "camera_analytics/samples/output_entities_validation.mp4",
    log_output_path: str = "camera_analytics/logs/entities_validation.jsonl",
    max_frames: Optional[int] = 200,
    confidence_threshold: float = 0.45,
    device: str = "cuda",
) -> None:
    """Run full pipeline validation with Entity Model & Payload SDK."""
    setup_logging()

    logger.info("=" * 70)
    logger.info("Sprint 9 -- Domain Entity Model & Payload SDK Validation")
    logger.info("=" * 70)

    # 1. Initialize Communication Layer & Log Publisher
    comm_manager = CommunicationManager.get_instance(queue_size=10000)

    log_path_obj = Path(log_output_path)
    log_pub = LogPublisher(
        name="entities_log_publisher",
        log_dir=str(log_path_obj.parent),
        filename_pattern=log_path_obj.name,
        rotate_daily=False,
    )
    comm_manager.publisher_manager.register_publisher(log_pub)
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
    camera = Camera("cam_entity_val", "Domain Entity Camera", video_path)
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

    camera_entity = EntityFactory.create_camera_entity(camera)

    logger.info("Processing frames with Domain Entity Model & Payload SDK...")
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

            # Manufacture strongly typed Frame Entity
            frame_entity = EntityFactory.create_frame_entity(frame_ctx, frame_count, packet.timestamp)

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

            # Build strongly typed AnalyticsPayload SDK object
            payload_sdk = AnalyticsPayload()
            payload_sdk.people.count = len(active_tracks)
            payload_sdk.people.confirmed_count = sum(1 for t in active_tracks if t.is_confirmed)
            payload_sdk.people.active_track_ids = [t.track_id for t in active_tracks]

            # Manufacture Track & Zone Entities for emitted events
            for evt in aggregated_res.all_events:
                associated_track_entity = None
                if evt.track_id is not None:
                    trk_obj = next((t for t in active_tracks if t.track_id == evt.track_id), None)
                    if trk_obj:
                        associated_track_entity = EntityFactory.create_track_entity(trk_obj)

                associated_zone_entity = None
                if evt.zone_id is not None:
                    z_obj = next((z for z in zones if z.zone_id == evt.zone_id), None)
                    if z_obj:
                        associated_zone_entity = EntityFactory.create_zone_entity(z_obj, current_state=ZoneState.ENTER)

                # Use EntitySerializer to transform Domain Entities + AnalyticsPayload into StandardAnalyticsEvent
                std_evt = EntitySerializer.build_analytics_event(
                    event_type=evt.event_type.name,
                    message=evt.message,
                    analytics_module=evt.module_name,
                    camera=camera_entity,
                    frame=frame_entity,
                    track=associated_track_entity,
                    zone=associated_zone_entity,
                    payload=payload_sdk,
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
                model_name="YOLO26m-Pose + Payload SDK",
                tracker_name=tracker.name.upper(),
            )

            writer.write(annotated_frame)

            if frame_count % 50 == 0:
                metrics = comm_manager.get_metrics()
                logger.info(
                    "FRAME %d | Entities Manufactured | Active Tracks: %d | Events Logged: %d",
                    frame_count,
                    len(active_tracks),
                    metrics.published_events,
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
    logger.info("DOMAIN ENTITY MODEL & PAYLOAD SDK SUMMARY REPORT")
    logger.info("-" * 70)
    logger.info("Total Frames Processed:      %d", frame_count)
    logger.info("Total Time Elapsed:          %.2f seconds", elapsed)
    logger.info("Average Processing Speed:    %.1f FPS", avg_fps)
    logger.info("Total Entities Manufactured: TrackEntity, CameraEntity, FrameEntity, ZoneEntity")
    logger.info("Events Serialized & Logged:  %d", metrics.published_events)
    logger.info("JSON Lines Log Saved to:     %s", log_output_path)
    logger.info("Rendered Output Saved to:    %s", output_path)
    logger.info("Sprint 9 Domain Entity Model & Payload SDK validation complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Domain Entity Model & Payload SDK Validation Tool")
    parser.add_argument(
        "--video",
        type=str,
        default="camera_analytics/samples/Screen_Recording_20260622_113428_EZVIZ.mp4",
        help="Path to input video file",
    )
    parser.add_argument("--max-frames", type=int, default=200, help="Max frames to process")
    args = parser.parse_args()

    validate_entities(video_path=args.video, max_frames=args.max_frames)
