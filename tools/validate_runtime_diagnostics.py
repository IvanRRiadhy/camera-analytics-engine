"""
Runtime Diagnostics & Profiling Framework Validation Tool (Sprint 10I).

Executes real video pipeline with 3 Analytics Modules profiling execution performance over 200 frames.
Collects frame latencies, per-plugin execution statistics, skip ratios, and health evaluations.
Prints official Runtime Diagnostics & Profiling Report.

Usage::

    python -m camera_analytics.tools.validate_runtime_diagnostics
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import Any, Optional

import cv2

from camera_analytics.adapters.detection.yolo_pose_adapter import YOLOPoseAdapter
from camera_analytics.adapters.tracking.botsort_adapter import BoTSORTAdapter
from camera_analytics.communication import CommunicationManager, LogPublisher
from camera_analytics.core import Config, EventBus, Pipeline
from camera_analytics.core.zone_engine import ZoneEngine
from camera_analytics.diagnostics import DiagnosticsReport
from camera_analytics.entities import AnalyticsPayload, EntitySerializer
from camera_analytics.models import Camera, Point, Zone, ZoneType
from camera_analytics.registry import ModuleDescriptor, ModuleManager, ModuleRegistry, ModuleState
from camera_analytics.runtime import AnalyticsRuntime
from camera_analytics.scene import SceneFactory
from camera_analytics.scheduler import ExecutionMode, ExecutionPolicy
from camera_analytics.sdk import (
    AnalyticsEvent,
    AnalyticsEventType,
    AnalyticsModule,
    AnalyticsResult,
)
from camera_analytics.sources.video_source import VideoSource
from camera_analytics.utils.visualizer import PoseVisualizer

logger = logging.getLogger("validate_runtime_diagnostics")


class ProfiledDemoPlugin(AnalyticsModule):
    """Analytics Module with configurable delay for diagnostics validation."""

    def __init__(self, name: str, simulated_delay_ms: float = 0.0) -> None:
        super().__init__(name=name, description=f"Profiled Demo Plugin ({name})")
        self.simulated_delay_ms = simulated_delay_ms

    def update(self, context: Any) -> Optional[AnalyticsResult]:
        return AnalyticsResult(module_name=self.name)

    def process(self, scene: Any) -> AnalyticsResult:
        if self.simulated_delay_ms > 0:
            time.sleep(self.simulated_delay_ms / 1000.0)

        events: list[AnalyticsEvent] = []

        if scene.frame.frame_index % 25 == 0:
            events.append(
                AnalyticsEvent(
                    event_id=f"evt_{self.name}_f{scene.frame.frame_index}",
                    module_name=self.name,
                    event_type=AnalyticsEventType.INFO,
                    message=f"[{self.name}] Profiled execution at frame {scene.frame.frame_index}",
                    timestamp=scene.frame.timestamp,
                    frame_index=scene.frame.frame_index,
                )
            )

        return AnalyticsResult(
            module_name=self.name,
            events=events,
            metrics={"simulated_delay_ms": self.simulated_delay_ms},
        )


def setup_logging() -> None:
    """Configure logging format."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )


def run_diagnostics_validation(
    video_path: str = "camera_analytics/samples/Screen_Recording_20260622_113428_EZVIZ.mp4",
    weights_path: str = "yolo26m-pose.pt",
    output_path: str = "camera_analytics/samples/output_diagnostics_validation.mp4",
    log_output_path: str = "camera_analytics/logs/diagnostics_validation.jsonl",
    max_frames: Optional[int] = 200,
    device: str = "cuda",
) -> None:
    """Run full pipeline validation with Runtime Diagnostics & Profiling."""
    setup_logging()

    logger.info("=" * 75)
    logger.info("Sprint 10I -- Runtime Diagnostics & Profiling Framework Validation")
    logger.info("=" * 75)

    # 1. Initialize Communication Layer
    comm_manager = CommunicationManager.get_instance(queue_size=10000)
    log_path_obj = Path(log_output_path)
    log_pub = LogPublisher(
        name="diagnostics_log_publisher",
        log_dir=str(log_path_obj.parent),
        filename_pattern=log_path_obj.name,
        rotate_daily=False,
    )
    comm_manager.publisher_manager.register_publisher(log_pub)
    comm_manager.initialize({})
    comm_manager.start()

    # 2. Initialize AI Adapters
    detector = YOLOPoseAdapter(confidence_threshold=0.45, iou_threshold=0.45)
    detector.load(weights_path, device=device)

    tracker = BoTSORTAdapter(track_high_thresh=0.5, match_thresh=0.8)
    tracker.initialize()

    # 3. Setup Polygon Zone & Zone Engine
    zone_main = Zone(
        zone_id="lobby_main",
        name="Main Entrance",
        zone_type=ZoneType.REGION,
        points=[Point(560, 860), Point(1100, 720), Point(1500, 1070), Point(500, 1070)],
        color=(0, 220, 0),
    )
    zones = [zone_main]
    zone_engine = ZoneEngine()

    # 4. Setup Framework Core Pipeline & Camera
    camera = Camera("cam_diag_val", "Profiled Camera", video_path)
    for z in zones:
        camera.add_zone(z)

    pipeline_cfg = Config.from_dict({
        "pipeline": {"process_every_n": 1},
        "track_manager": {"max_history_length": 150, "confirm_after_n": 3, "max_lost_age": 30},
    })
    event_bus = EventBus()
    pipeline = Pipeline(pipeline_cfg, camera, event_bus)
    pipeline.start()

    # 5. Setup AnalyticsRuntime Kernel and Register Profiled Modules
    runtime_kernel = AnalyticsRuntime()

    mod_pc = ProfiledDemoPlugin("people_counter", simulated_delay_ms=1.5)
    mod_crowd = ProfiledDemoPlugin("crowd_density", simulated_delay_ms=3.0)
    mod_heatmap = ProfiledDemoPlugin("heatmap", simulated_delay_ms=6.0)

    desc_pc = ModuleDescriptor(
        module_id="people_counter",
        module_name="People Counter",
        priority=10,
        capabilities=["TRACKING", "POSE", "ZONE"],
        execution_policy=ExecutionPolicy(execution_mode=ExecutionMode.EVERY_FRAME),
    )
    desc_crowd = ModuleDescriptor(
        module_id="crowd_density",
        module_name="Crowd Density",
        priority=20,
        capabilities=["TRACKING", "ZONE"],
        execution_policy=ExecutionPolicy(execution_mode=ExecutionMode.INTERVAL, interval=5),
    )
    desc_heatmap = ModuleDescriptor(
        module_id="heatmap",
        module_name="Heatmap Analytics",
        priority=30,
        capabilities=["TRACKING", "GROUND_POINT"],
        execution_policy=ExecutionPolicy(execution_mode=ExecutionMode.INTERVAL, interval=10),
    )

    runtime_kernel.register_module(mod_pc, desc_pc)
    runtime_kernel.register_module(mod_crowd, desc_crowd)
    runtime_kernel.register_module(mod_heatmap, desc_heatmap)

    runtime_kernel.initialize()
    runtime_kernel.start()

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

    logger.info("Processing frames with Runtime Diagnostics & Profiling...")
    logger.info("-" * 75)

    try:
        while source.is_open:
            packet = source.read()
            if packet is None or packet.image is None:
                break

            frame_count += 1
            frame = packet.image

            # Inference & Tracking
            det_res = detector.detect(frame)
            trk_res = tracker.track(frame, det_res)

            # Core Pipeline & TrackManager processing
            frame_ctx = pipeline.process(frame, trk_res.results)

            runtime = pipeline.runtime
            active_tracks = runtime.track_manager.get_active() if runtime else []

            # Zone Engine Spatial Evaluation
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

            # Dispatch Scene snapshot (Diagnostics passively collects metrics)
            aggregated_res = runtime_kernel.process_scene(scene)

            # Enqueue events to Communication Layer
            payload_sdk = AnalyticsPayload()
            payload_sdk.people.count = len(scene.tracks)
            payload_sdk.people.active_track_ids = [t.track_id for t in scene.tracks]

            for evt in aggregated_res.all_events:
                std_evt = EntitySerializer.build_analytics_event(
                    event_type=evt.event_type.name,
                    message=evt.message,
                    analytics_module=evt.module_name,
                    camera=scene.camera,
                    frame=scene.frame,
                    payload=payload_sdk,
                )
                comm_manager.enqueue(std_evt)

            # Render overlay
            executed_in_frame = list(aggregated_res.results.keys())
            annotated_frame = visualizer.draw_tracks(
                frame=frame,
                tracks=active_tracks,
                zones=zones,
                track_zone_states=zone_result.track_states,
                frame_id=frame_count,
                fps=fps,
                device=f"CUDA ({detector.name})",
                model_name=f"Profiled: {','.join(executed_in_frame)}",
                tracker_name=tracker.name.upper(),
            )
            writer.write(annotated_frame)

            if frame_count % 50 == 0:
                snap_report = runtime_kernel.get_diagnostics_report()
                logger.info(
                    "FRAME %d | Health: %s | FPS: %.1f | Avg Latency: %.2f ms",
                    frame_count,
                    snap_report.health.name,
                    snap_report.runtime_metrics.fps,
                    snap_report.runtime_metrics.average_latency_ms,
                )

            if max_frames is not None and frame_count >= max_frames:
                logger.info("Reached maximum requested frames limit (%d)", max_frames)
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
    metrics = comm_manager.get_metrics()

    # Generate final DiagnosticsReport
    diag_report = runtime_kernel.get_diagnostics_report()
    report_dict = diag_report.to_dict()

    logger.info("=" * 75)
    logger.info("RUNTIME DIAGNOSTICS & PROFILING REPORT")
    logger.info("=" * 75)
    logger.info("Runtime Health Status:        %s", report_dict["runtime_health"])
    logger.info("Total Frames Processed:      %d frames", report_dict["runtime_metrics"]["total_frames"])
    logger.info("Average Processing Latency:  %.3f ms", report_dict["runtime_metrics"]["average_latency_ms"])
    logger.info("Peak Frame Latency:          %.3f ms", report_dict["runtime_metrics"]["peak_latency_ms"])
    logger.info("Average Frame Rate:          %.1f FPS", report_dict["runtime_metrics"]["fps"])
    logger.info("Events Published & Logged:   %d events", metrics.published_events)
    logger.info("-" * 75)
    logger.info("PROFILING HIGHLIGHTS:")
    logger.info("  - Slowest Module (Peak Latency):    %s", report_dict["slowest_plugin"] or "N/A")
    logger.info("  - Fastest Module (Avg Latency):     %s", report_dict["fastest_plugin"] or "N/A")
    logger.info("  - Top Event Producer:               %s", report_dict["highest_event_producer"] or "N/A")
    logger.info("  - Highest Skip Ratio Module:        %s", report_dict["highest_skip_ratio_plugin"] or "N/A")
    logger.info("-" * 75)
    logger.info("PER-MODULE DETAILED METRICS:")
    for pm in diag_report.plugin_metrics:
        logger.info(
            "  - Module: '%-18s' | Execs: %3d | Skips: %3d | SkipRatio: %5.1f%% | Avg: %6.3f ms | Max: %6.3f ms | Events: %2d | Errors: %d",
            pm.module_id,
            pm.executed_count,
            pm.skipped_count,
            pm.skip_ratio * 100.0,
            pm.average_execution_time_ms,
            pm.max_execution_time_ms,
            pm.published_events,
            pm.error_count,
        )
    logger.info("=" * 75)
    logger.info("Sprint 10I Runtime Diagnostics & Profiling Framework validation complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Runtime Diagnostics & Profiling Validation Tool")
    parser.add_argument(
        "--video",
        type=str,
        default="camera_analytics/samples/Screen_Recording_20260622_113428_EZVIZ.mp4",
        help="Path to input video file",
    )
    parser.add_argument("--max-frames", type=int, default=200, help="Max frames to process")
    args = parser.parse_args()

    run_diagnostics_validation(video_path=args.video, max_frames=args.max_frames)
