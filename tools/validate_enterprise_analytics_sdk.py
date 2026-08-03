"""
Enterprise Analytics SDK Validation Tool (Sprint 12.0).

Executes real video pipeline with all 8 Enterprise Analytics Plugins loaded dynamically into AnalyticsRuntime Kernel over 200 frames.
Transforms immutable Scene snapshots into schema-versioned StandardAnalyticsEvents dispatched to CommunicationManager.
Prints official Sprint 12.0 Enterprise Analytics SDK Report.

Usage::

    python -m camera_analytics.tools.validate_enterprise_analytics_sdk
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
from camera_analytics.communication import CommunicationManager, LogPublisher
from camera_analytics.core import Config, EventBus, Pipeline
from camera_analytics.core.zone_engine import ZoneEngine
from camera_analytics.entities import AnalyticsPayload, EntitySerializer
from camera_analytics.models import Camera, Point, Zone, ZoneType
from camera_analytics.runtime import AnalyticsRuntime
from camera_analytics.scene import SceneFactory
from camera_analytics.sdk import StandardAnalyticsEvent
from camera_analytics.sources.video_source import VideoSource
from camera_analytics.utils.visualizer import PoseVisualizer

logger = logging.getLogger("validate_enterprise_analytics_sdk")


def setup_logging() -> None:
    """Configure logging format."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )


def run_enterprise_sdk_validation(
    video_path: str = "camera_analytics/samples/Screen_Recording_20260622_113428_EZVIZ.mp4",
    weights_path: str = "yolo26m-pose.pt",
    output_path: str = "camera_analytics/samples/output_enterprise_sdk_validation.mp4",
    log_output_path: str = "camera_analytics/logs/enterprise_sdk_validation.jsonl",
    max_frames: Optional[int] = 200,
    device: str = "cuda",
) -> None:
    """Run full pipeline validation for Enterprise Analytics SDK & Standard Event Framework."""
    setup_logging()

    logger.info("=" * 80)
    logger.info("Sprint 12.0 -- Enterprise Analytics SDK & Standard Event Framework Validation")
    logger.info("=" * 80)

    # 1. Communication Layer
    comm_manager = CommunicationManager.get_instance(queue_size=10000)
    log_path_obj = Path(log_output_path)
    log_pub = LogPublisher(
        name="enterprise_sdk_log_publisher",
        log_dir=str(log_path_obj.parent),
        filename_pattern=log_path_obj.name,
        rotate_daily=False,
    )
    comm_manager.publisher_manager.register_publisher(log_pub)
    comm_manager.initialize({})
    comm_manager.start()

    # 2. AI Adapters
    detector = YOLOPoseAdapter(confidence_threshold=0.45, iou_threshold=0.45)
    detector.load(weights_path, device=device)

    tracker = BoTSORTAdapter(track_high_thresh=0.5, match_thresh=0.8)
    tracker.initialize()

    # 3. Spatial Zone & Engine
    zone_lobby = Zone(
        zone_id="lobby_main",
        name="Main Entrance Lobby",
        zone_type=ZoneType.REGION,
        points=[Point(560, 860), Point(1100, 720), Point(1500, 1070), Point(500, 1070)],
        color=(0, 220, 0),
    )
    zones = [zone_lobby]
    zone_engine = ZoneEngine()

    # 4. Core Pipeline & Camera
    camera = Camera("cam_ent_sdk", "Main Entrance Cam", video_path)
    for z in zones:
        camera.add_zone(z)

    pipeline_cfg = Config.from_dict({
        "pipeline": {"process_every_n": 1},
        "track_manager": {"max_history_length": 150, "confirm_after_n": 3, "max_lost_age": 30},
    })
    event_bus = EventBus()
    pipeline = Pipeline(pipeline_cfg, camera, event_bus)
    pipeline.start()

    # 5. AnalyticsRuntime Kernel & Dynamic Plugin Discovery
    runtime_kernel = AnalyticsRuntime()

    logger.info("Discovering and dynamically loading Enterprise Analytics Plugins...")
    loading_report = runtime_kernel.load_plugins_from_directory("camera_analytics/plugins")
    logger.info(
        "Plugin Loading Complete: %d loaded, %d rejected out of %d discovered manifests",
        loading_report.loaded_count,
        loading_report.rejected_count,
        loading_report.found_count,
    )

    runtime_kernel.initialize()
    runtime_kernel.start()

    # 6. Video Source & Writer
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
    total_standard_events = 0
    event_breakdown: dict[str, int] = {}

    logger.info("Processing frames with 8 Enterprise Analytics Plugins...")
    logger.info("-" * 80)

    try:
        while source.is_open:
            packet = source.read()
            if packet is None or packet.image is None:
                break

            frame_count += 1
            frame = packet.image

            # Detection & Tracking
            det_res = detector.detect(frame)
            trk_res = tracker.track(frame, det_res)

            # Core Pipeline
            frame_ctx = pipeline.process(frame, trk_res.results)

            runtime = pipeline.runtime
            active_tracks = runtime.track_manager.get_active() if runtime else []

            # Spatial Zone Evaluation
            zone_result = zone_engine.process(
                tracks=active_tracks,
                zones=zones,
                frame_index=frame_count,
                timestamp=packet.timestamp,
            )

            # Manufacture Immutable Scene Snapshot
            scene = SceneFactory.create_scene(
                runtime_state=runtime,
                frame_context=frame_ctx,
                zone_result=zone_result,
                zones=zones,
                frame_index=frame_count,
                timestamp=packet.timestamp,
            )

            # Dispatch Scene to Analytics Runtime Kernel
            aggregated_res = runtime_kernel.process_scene(scene)

            # Dispatch events to Communication Layer
            payload_sdk = AnalyticsPayload()
            payload_sdk.people.count = len(scene.tracks)
            payload_sdk.people.active_track_ids = [t.track_id for t in scene.tracks]

            for evt in aggregated_res.all_events:
                total_standard_events += 1
                evt_dict = evt.data if isinstance(evt.data, dict) else {}
                evt_type = evt_dict.get("event_type", evt.event_type.name)
                event_breakdown[evt_type] = event_breakdown.get(evt_type, 0) + 1

                tr_id = evt_dict.get("track_id", evt.track_id)
                z_id = evt_dict.get("zone_id", evt.zone_id)
                z_name = evt_dict.get("zone_name")
                sev = evt_dict.get("severity", "INFO")
                corr_id = evt_dict.get("correlation_id")
                evt_payload = evt_dict.get("payload", evt_dict)

                # Lookup track or zone entity from scene if available
                track_ent = scene.get_track_by_id(tr_id) if tr_id is not None else None
                zone_ent = scene.get_zone_by_id(z_id) if z_id is not None else None

                std_evt = EntitySerializer.build_analytics_event(
                    event_type=evt_type,
                    message=evt.message,
                    analytics_module=evt.module_name,
                    camera=scene.camera,
                    frame=scene.frame,
                    track=track_ent,
                    zone=zone_ent,
                    payload=evt_payload,
                    severity=sev,
                    correlation_id=corr_id,
                    track_id=tr_id,
                    zone_id=z_id,
                    zone_name=z_name,
                )
                comm_manager.enqueue(std_evt)

            # Visual overlay
            annotated_frame = visualizer.draw_tracks(
                frame=frame,
                tracks=active_tracks,
                zones=zones,
                track_zone_states=zone_result.track_states,
                frame_id=frame_count,
                fps=fps,
                device=f"CUDA ({detector.name})",
                model_name=f"Ent SDK ({len(aggregated_res.results)} Plugins)",
                tracker_name=tracker.name.upper(),
            )
            writer.write(annotated_frame)

            if frame_count % 50 == 0:
                diag_snap = runtime_kernel.get_diagnostics_report()
                logger.info(
                    "FRAME %d | Health: %s | Active Tracks: %d | Generated Events: %d | FPS: %.1f",
                    frame_count,
                    diag_snap.health.name,
                    len(active_tracks),
                    total_standard_events,
                    diag_snap.runtime_metrics.fps,
                )

            if max_frames is not None and frame_count >= max_frames:
                logger.info("Reached requested frame limit (%d)", max_frames)
                break

    finally:
        source.release()
        writer.release()
        runtime_kernel.stop()
        runtime_kernel.dispose()
        comm_manager.stop()
        comm_manager.dispose()
        pipeline.stop()
        detector.release()
        tracker.reset()
        zone_engine.reset()

    elapsed = time.monotonic() - start_time
    avg_fps = frame_count / max(elapsed, 0.001)

    diag_report = runtime_kernel.get_diagnostics_report()

    logger.info("=" * 80)
    logger.info("SPRINT 12.0 ENTERPRISE ANALYTICS SDK REPORT")
    logger.info("=" * 80)
    logger.info("Total Frames Processed:          %d frames", frame_count)
    logger.info("Total Time Elapsed:              %.2f seconds", elapsed)
    logger.info("Average Processing Speed:        %.1f FPS", avg_fps)
    logger.info("Active Analytics Plugins Loaded: %d plugins", loading_report.loaded_count)
    logger.info("Total Standard Events Generated: %d events", total_standard_events)
    logger.info("-" * 80)
    logger.info("ENTERPRISE EVENT TYPE BREAKDOWN:")
    for etype, cnt in sorted(event_breakdown.items()):
        logger.info("  - Event Type: '%-25s' | Generated Count: %d", etype, cnt)
    logger.info("-" * 80)
    logger.info("PLUGIN EXECUTION METRICS:")
    for pm in diag_report.plugin_metrics:
        logger.info(
            "  - Plugin: '%-22s' | Execs: %3d | Skips: %3d | Avg Latency: %6.3f ms | Events: %2d",
            pm.module_id,
            pm.executed_count,
            pm.skipped_count,
            pm.average_execution_time_ms,
            pm.published_events,
        )
    logger.info("=" * 80)
    logger.info("Sprint 12.0 Enterprise Analytics SDK & Standard Event Framework validation complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enterprise Analytics SDK Validation Tool")
    parser.add_argument(
        "--video",
        type=str,
        default="camera_analytics/samples/Screen_Recording_20260622_113428_EZVIZ.mp4",
        help="Path to input video file",
    )
    parser.add_argument("--max-frames", type=int, default=200, help="Max frames to process")
    args = parser.parse_args()

    run_enterprise_sdk_validation(video_path=args.video, max_frames=args.max_frames)
