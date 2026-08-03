"""
Continuous Live RTSP Analytics & Event Logger Tool.

Runs continuous real-time video analytics on a live RTSP CCTV camera stream without frame limits.
Executes YOLO26m-Pose -> BoTSORT -> Pipeline -> ZoneEngine -> Analytics Engine -> Communication Layer,
writing all generated Analytics Events in real-time to a JSON Lines log file (`camera_analytics/logs/live_events.jsonl`).

Usage::

    python -m camera_analytics.tools.run_live_rtsp_analytics

Or with custom parameters::

    python -m camera_analytics.tools.run_live_rtsp_analytics --rtsp-url "rtsp://admin:Admin1234@192.168.1.64/Streaming/channels/2" --log-file "camera_analytics/logs/my_events.jsonl"
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
from camera_analytics.sources.rtsp_source import RTSPSource
from camera_analytics.utils.resource_monitor import BenchmarkCollector
from camera_analytics.utils.visualizer import PoseVisualizer

logger = logging.getLogger("run_live_rtsp_analytics")


def setup_logging() -> None:
    """Configure clean console logging."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )


def run_live_rtsp_analytics(
    rtsp_url: str = "rtsp://admin:Admin1234@192.168.1.64/Streaming/channels/2",
    weights_path: str = "yolo26m-pose.pt",
    log_file_path: str = "camera_analytics/logs/live_events.jsonl",
    output_video_path: Optional[str] = None,
    device: str = "cuda",
    confidence_threshold: float = 0.45,
    show_preview: bool = False,
) -> None:
    """Run continuous live RTSP camera analytics until manually stopped (Ctrl+C).

    Args:
        rtsp_url: RTSP connection URL.
        weights_path: Path to YOLO weights file (.pt).
        log_file_path: Output path for JSON Lines (.jsonl) event log.
        output_video_path: Optional path to save recorded annotated MP4 video.
        device: Compute device ('cuda' or 'cpu').
        confidence_threshold: Detector confidence threshold.
        show_preview: Whether to open interactive OpenCV preview window.
    """
    setup_logging()

    logger.info("=" * 75)
    logger.info("Continuous Live RTSP Camera Analytics & Event Logger")
    logger.info("=" * 75)
    logger.info("RTSP Stream URL: %s", rtsp_url)
    logger.info("Event Log Output: %s", log_file_path)
    logger.info("Compute Device:  %s", device.upper())
    logger.info("Press Ctrl+C to stop processing cleanly.")
    logger.info("=" * 75)

    # 1. Initialize Event Communication Layer & Log Publisher
    comm_manager = CommunicationManager.get_instance(queue_size=10000)

    log_path_obj = Path(log_file_path)
    log_pub = LogPublisher(
        name="live_rtsp_log_publisher",
        log_dir=str(log_path_obj.parent),
        filename_pattern=log_path_obj.name,
        rotate_daily=True,
    )
    comm_manager.publisher_manager.register_publisher(log_pub)
    comm_manager.initialize({})
    comm_manager.start()

    collector = BenchmarkCollector(camera_name=f"Live RTSP Camera ({rtsp_url})")

    # 2. Initialize AI Models
    detector = YOLOPoseAdapter(
        confidence_threshold=confidence_threshold,
        iou_threshold=0.45,
    )
    try:
        detector.load(weights_path, device=device)
    except Exception as exc:
        logger.error("Failed to load YOLO model: %s", exc)
        return

    tracker = BoTSORTAdapter(track_high_thresh=0.5, match_thresh=0.8)
    tracker.initialize()

    # 3. Setup RTSPSource Connection
    source = RTSPSource(
        rtsp_url=rtsp_url,
        reconnect_delay=3.0,
        buffer_size=1,
    )
    source.open()

    # 4. Setup Polygon Zones & Zone Engine
    zone_critical = Zone(
        zone_id="entrance_main",
        name="Main Entrance",
        
        zone_type=ZoneType.REGION,
        points=[
            Point(1350, 630),
            Point(2120, 810),
            Point(2380, 795),
            # Point(800, 650),
        ],
        color=(255, 0, 255),
    )
    zone_main = Zone(
        zone_id="critical_area",
        name="Area Kritis",
        zone_type=ZoneType.REGION,
        points=[
            Point(700, 1250),
            Point(370, 1550),
            Point(468, 1620),
            Point(1899, 1620),
            Point(2020, 1250),
        ],
        color=(0, 220, 0),
    )
    zone_forbidden = Zone(
        zone_id="forbidden_area",
        name="Forbidden Area",
        zone_type=ZoneType.REGION,
        points=[
            # Point(700, 1250),
            Point(1750, 250),
            Point(1750, 520),
            Point(1999, 520),
            Point(1999, 250),
        ],
        color=(255, 0, 0),
    )
    zones = [zone_critical, zone_main, zone_forbidden]
    zone_engine = ZoneEngine()

    # 5. Setup Framework Core Pipeline & Camera
    camera = Camera("cam_live_cctv", "Live CCTV Camera", rtsp_url)
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

    # 6. Setup Analytics Engine & Register Plugins
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

    # 7. Setup Visualizer & Optional VideoWriter
    visualizer = PoseVisualizer(keypoint_threshold=0.5)
    writer: Optional[cv2.VideoWriter] = None

    frame_count = 0
    total_events_logged = 0
    track_history_ids: set[int] = set()

    logger.info("Live RTSP Stream Connected. Streaming & analyzing frames continuously...")
    logger.info("-" * 75)

    try:
        while source.is_open:
            t0 = time.monotonic()

            packet = source.read()
            if packet is None or packet.image is None:
                time.sleep(0.01)
                continue

            frame = packet.image
            h, w = frame.shape[:2]
            collector.input_resolution = (w, h)
            collector.processing_resolution = (w, h)

            if writer is None and output_video_path:
                Path(output_video_path).parent.mkdir(parents=True, exist_ok=True)
                fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                writer = cv2.VideoWriter(output_video_path, fourcc, 25.0, (w, h))

            t1 = time.monotonic()
            capture_ms = (t1 - t0) * 1000.0

            # Step 1: AI Pose Detection
            det_res = detector.detect(frame)
            t2 = time.monotonic()
            detection_ms = (t2 - t1) * 1000.0

            # Step 2: BoTSORT Association
            trk_res = tracker.track(frame, det_res)
            t3 = time.monotonic()
            tracking_ms = (t3 - t2) * 1000.0

            # Step 3: Pipeline & TrackManager processing
            frame_ctx = pipeline.process(frame, trk_res.results)

            runtime = pipeline.runtime
            active_tracks = runtime.track_manager.get_active() if runtime else []

            newly_created = [t for t in active_tracks if t.track_id not in track_history_ids]
            for t in newly_created:
                track_history_ids.add(t.track_id)

            # Step 4: ZoneEngine Spatial Analysis
            zone_result = zone_engine.process(
                tracks=active_tracks,
                zones=zones,
                frame_index=frame_count + 1,
                timestamp=packet.timestamp,
            )

            # Step 5: Analytics Engine Processing
            analytics_ctx = AnalyticsContext(
                frame_context=frame_ctx,
                runtime_state=runtime,
                track_manager=runtime.track_manager if runtime else None,
                active_tracks=active_tracks,
                zones=zones,
                zone_result=zone_result,
                frame_index=frame_count + 1,
                timestamp=packet.timestamp,
            )

            aggregated_res = analytics_manager.process(
                context=analytics_ctx,
                tracks_created=newly_created,
            )

            # Step 6: Emit Analytics Events to Communication Layer (Log File)
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
                total_events_logged += 1

            # Step 7: Render Visual Overlays
            annotated_frame = visualizer.draw_tracks(
                frame=frame,
                tracks=active_tracks,
                zones=zones,
                track_zone_states=zone_result.track_states,
                frame_id=frame_count + 1,
                fps=0.0,
                device=f"CUDA ({detector.name})",
                model_name="YOLO26m-Pose",
                tracker_name=tracker.name.upper(),
                benchmark_collector=collector,
            )

            t4 = time.monotonic()
            rendering_ms = (t4 - t3) * 1000.0

            frame_count += 1
            collector.record_frame(
                frame_id=frame_count,
                capture_ms=capture_ms,
                detection_ms=detection_ms,
                tracking_ms=tracking_ms,
                rendering_ms=rendering_ms,
            )

            if writer:
                writer.write(annotated_frame)

            if show_preview:
                try:
                    cv2.imshow("Live CCTV Analytics & Event Logger", annotated_frame)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        logger.info("Preview window closed by user keypress 'q'")
                        break
                except Exception:
                    show_preview = False

            if frame_count % 100 == 0:
                comm_metrics = comm_manager.get_metrics()
                logger.info(
                    "FRAME #%d | Active Tracks: %d | Events Logged: %d | Queue: %d | GPU VRAM: %.0fMB",
                    frame_count,
                    len(active_tracks),
                    comm_metrics.published_events,
                    comm_metrics.queue_size,
                    collector.latest_hw.vram_used_mb,
                )

    except KeyboardInterrupt:
        logger.info("\nLive RTSP Analytics stopped cleanly by user (Ctrl+C).")
    finally:
        source.release()
        if writer:
            writer.release()
        if show_preview:
            try:
                cv2.destroyAllWindows()
            except Exception:
                pass
        analytics_manager.stop()
        analytics_manager.dispose()
        comm_manager.stop()
        comm_manager.dispose()
        pipeline.stop()
        detector.release()
        tracker.reset()
        zone_engine.reset()

    # Final Benchmark & Event Summary Report
    logger.info("\n" + collector.generate_report())
    logger.info("-" * 75)
    logger.info("LIVE ANALYTICS EVENT LOGGING SUMMARY")
    logger.info("-" * 75)
    logger.info("Total Video Frames Processed: %d", frame_count)
    logger.info("Total Events Written to Log: %d", total_events_logged)
    logger.info("JSON Lines Log File Path:    %s", str(Path(log_file_path).resolve()))
    logger.info("Live RTSP Analytics process finished.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Continuous Live RTSP Analytics & Event Logger")
    parser.add_argument(
        "--rtsp-url",
        type=str,
        default="rtsp://admin:Admin1234@192.168.1.64/Streaming/channels/2",
        help="RTSP camera stream connection URL",
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default="camera_analytics/logs/live_events.jsonl",
        help="Output path for JSON Lines (.jsonl) event log file",
    )
    parser.add_argument(
        "--record-video",
        type=str,
        default=None,
        help="Optional path to save annotated MP4 video (e.g. camera_analytics/samples/output_live_rec.mp4)",
    )
    parser.add_argument("--device", type=str, default="cuda", help="Compute device ('cuda' or 'cpu')")
    parser.add_argument("--show-preview", action="store_true", help="Display live preview window")

    args = parser.parse_args()

    run_live_rtsp_analytics(
        rtsp_url=args.rtsp_url,
        weights_path="yolo26m-pose.pt",
        log_file_path=args.log_file,
        output_video_path=args.record_video,
        device=args.device,
        show_preview=args.show_preview,
    )
