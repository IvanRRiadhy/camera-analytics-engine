"""
Sprint 12.0.1 — Enterprise Event Serialization Optimization CLI Validation & Storage Estimation Tool.

Executes a 200-frame video pipeline processing with 8 dynamic Enterprise Analytics Plugins.
Measures payload sizes across Summary, Standard, and Full detail levels.
Calculates storage usage projections for 10, 50, and 100 enterprise camera deployments.
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

from camera_analytics.adapters.detection.yolo_pose_adapter import YOLOPoseAdapter
from camera_analytics.adapters.tracking.botsort_adapter import BoTSORTAdapter
from camera_analytics.communication import AnalyticsEventSerializer, CommunicationManager, EventDetailLevel, LogPublisher
from camera_analytics.core import Config, EventBus, Pipeline
from camera_analytics.core.zone_engine import ZoneEngine
from camera_analytics.entities import AnalyticsPayload, EntitySerializer
from camera_analytics.models import Camera, Point, Zone, ZoneType
from camera_analytics.runtime import AnalyticsRuntime
from camera_analytics.scene import SceneFactory
from camera_analytics.sdk import StandardAnalyticsEvent
from camera_analytics.sources.video_source import VideoSource

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("validate_event_serialization_optimization")

SAMPLE_VIDEO_PATH = "camera_analytics/samples/Screen_Recording_20260622_113428_EZVIZ.mp4"
LOG_OUTPUT_DIR = "camera_analytics/logs"
FRAME_LIMIT = 200


def main() -> None:
    logger.info("================================================================================")
    logger.info("Sprint 12.0.1 -- Enterprise Event Serialization Optimization & Storage Benchmark")
    logger.info("================================================================================")

    # Initialize Communication Layer with LogPublisher in summary detail mode
    comm_manager = CommunicationManager.get_instance(queue_size=10000)
    log_pub = LogPublisher(
        name="opt_log_publisher",
        enabled=True,
        log_dir=LOG_OUTPUT_DIR,
        filename_pattern="events_optimized_summary.jsonl",
        rotate_daily=False,
        detail_level="summary",
    )
    comm_manager.publisher_manager.register_publisher(log_pub)
    comm_manager.initialize({})
    comm_manager.start()

    # Define Spatial Zone
    zone_lobby = Zone(
        zone_id="lobby_main",
        name="Main Entrance Lobby",
        zone_type=ZoneType.REGION,
        points=[Point(560, 860), Point(1100, 720), Point(1500, 1070), Point(500, 1070)],
        color=(0, 220, 0),
    )
    zones = [zone_lobby]

    # Initialize AI Components
    detector = YOLOPoseAdapter(confidence_threshold=0.35, iou_threshold=0.45)
    detector.load("yolo26m-pose.pt", device="cuda")

    tracker = BoTSORTAdapter(track_high_thresh=0.5, match_thresh=0.8)
    tracker.initialize()

    runtime_kernel = AnalyticsRuntime()

    # Discover and Load Plugins
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

    camera = Camera("cam_opt_sdk", "Main Entrance Cam", SAMPLE_VIDEO_PATH)
    for z in zones:
        camera.add_zone(z)

    pipeline_cfg = Config.from_dict({
        "pipeline": {"process_every_n": 1},
        "track_manager": {"max_history_length": 150, "confirm_after_n": 3, "max_lost_age": 30},
    })
    event_bus = EventBus()
    pipeline = Pipeline(config=pipeline_cfg, camera=camera, event_bus=event_bus)
    pipeline.start()

    zone_engine = ZoneEngine()
    source = VideoSource(SAMPLE_VIDEO_PATH)
    source.open()

    frame_count = 0
    generated_events = []
    start_time = time.time()

    logger.info("Processing 200 frames to capture event payloads...")
    while source.is_open and frame_count < FRAME_LIMIT:
        packet = source.read()
        if packet is None:
            break

        frame_count += 1
        frame = packet.image

        det_res = detector.detect(frame)
        trk_res = tracker.track(frame, det_res)

        frame_ctx = pipeline.process(frame, trk_res.results)
        runtime = pipeline.runtime
        active_tracks = runtime.track_manager.get_active() if runtime else []

        zone_result = zone_engine.process(
            tracks=active_tracks,
            zones=zones,
            frame_index=frame_count,
            timestamp=packet.timestamp,
        )

        scene = SceneFactory.create_scene(
            runtime_state=runtime,
            frame_context=frame_ctx,
            zone_result=zone_result,
            zones=zones,
            frame_index=frame_count,
            timestamp=packet.timestamp,
        )

        aggregated_res = runtime_kernel.process_scene(scene)

        for evt in aggregated_res.all_events:
            evt_dict = evt.data if isinstance(evt.data, dict) else {}
            evt_type = evt_dict.get("event_type", evt.event_type.name)
            tr_id = evt_dict.get("track_id", evt.track_id)
            z_id = evt_dict.get("zone_id", evt.zone_id)
            z_name = evt_dict.get("zone_name")
            sev = evt_dict.get("severity", "INFO")
            corr_id = evt_dict.get("correlation_id")
            evt_payload = evt_dict.get("payload", evt_dict)

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
            generated_events.append(std_evt)
            comm_manager.enqueue(std_evt)

    elapsed_sec = max(0.001, time.time() - start_time)
    fps = frame_count / elapsed_sec

    # Shutdown
    source.release()
    pipeline.stop()
    runtime_kernel.stop()
    runtime_kernel.dispose()
    comm_manager.stop()
    comm_manager.dispose()
    detector.release()
    tracker.reset()

    total_events = len(generated_events)

    # Size Measurements across Detail Levels
    summary_bytes = [len(AnalyticsEventSerializer.serialize(e, detail_level=EventDetailLevel.SUMMARY).encode("utf-8")) for e in generated_events]
    standard_bytes = [len(AnalyticsEventSerializer.serialize(e, detail_level=EventDetailLevel.STANDARD).encode("utf-8")) for e in generated_events]
    full_bytes = [len(AnalyticsEventSerializer.serialize(e, detail_level=EventDetailLevel.FULL).encode("utf-8")) for e in generated_events]

    avg_summary = sum(summary_bytes) / max(1, total_events)
    avg_standard = sum(standard_bytes) / max(1, total_events)
    avg_full = sum(full_bytes) / max(1, total_events)

    evts_per_frame = total_events / max(1, frame_count)
    # Estimate event rate per camera: 30 FPS stream with 10 FPS evaluation = 10 frames/sec/cam * evts_per_frame
    events_per_sec_per_cam = 10.0 * evts_per_frame
    events_per_hour_per_cam = events_per_sec_per_cam * 3600.0

    logger.info("================================================================================")
    logger.info("SPRINT 12.0.1 EVENT SERIALIZATION BENCHMARK REPORT")
    logger.info("================================================================================")
    logger.info(f"Total Frames Processed:          {frame_count} frames")
    logger.info(f"Processing Speed:                {fps:.1f} FPS")
    logger.info(f"Total Events Generated:          {total_events} events ({evts_per_frame:.2f} events/frame)")
    logger.info("--------------------------------------------------------------------------------")
    logger.info("PAYLOAD SIZE COMPARISON ACROSS LOGGING DETAIL LEVELS:")
    logger.info(f"  - SUMMARY  (Business Default): Avg {avg_summary:.1f} bytes/event  (Target: 300-700B)")
    logger.info(f"  - STANDARD (Production Debug): Avg {avg_standard:.1f} bytes/event (Target: 700-1200B)")
    logger.info(f"  - FULL     (Dev Telemetry):    Avg {avg_full:.1f} bytes/event     (Target: >1800B)")
    logger.info(f"  - Payload Storage Reduction:   -{(1.0 - avg_summary / avg_full) * 100:.1f}% reduction (Summary vs Full)")
    logger.info("--------------------------------------------------------------------------------")
    logger.info("ENTERPRISE MULTI-CAMERA STORAGE PROJECTIONS (SUMMARY DETAIL MODE):")

    for num_cams in [10, 50, 100]:
        hourly_mb = (events_per_hour_per_cam * num_cams * avg_summary) / (1024 * 1024)
        daily_gb = (hourly_mb * 24) / 1024
        monthly_gb = daily_gb * 30

        logger.info(f"  [{num_cams:3d} CAMERAS]")
        logger.info(f"    - Storage / Hour:  {hourly_mb:7.2f} MB / hr")
        logger.info(f"    - Storage / Day:   {daily_gb:7.2f} GB / day")
        logger.info(f"    - Storage / Month: {monthly_gb:7.2f} GB / month")

    logger.info("================================================================================")
    logger.info("Sprint 12.0.1 Enterprise Event Serialization Optimization complete.")


if __name__ == "__main__":
    main()
