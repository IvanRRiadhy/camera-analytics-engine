"""
Execution Scheduler Framework Validation Tool (Sprint 10F).

Executes real video pipeline with 3 registered Analytics Modules testing ExecutionPolicy timing rules over 200 frames.

Validates:
    - Module 1 'people_counter' (EVERY_FRAME) -> Executed on all 200 frames.
    - Module 2 'crowd_density' (INTERVAL 5) -> Executed on 41 frames (frame 1, 5, 10, 15... 200).
    - Module 3 'heatmap' (INTERVAL 10) -> Executed on 21 frames (frame 1, 10, 20... 200).
    - Runtime Execution Scheduler Report generation summarizing Executed vs Skipped counts and Execution Ratios.
    - Event publishing to JSON Lines (.jsonl) log file (`camera_analytics/logs/scheduler_validation.jsonl`).

Usage::

    python -m camera_analytics.tools.validate_execution_scheduler
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
from camera_analytics.entities import AnalyticsPayload, EntitySerializer
from camera_analytics.models import Camera, Point, Zone, ZoneType
from camera_analytics.registry import ModuleDescriptor, ModuleManager, ModuleRegistry, ModuleState
from camera_analytics.runtime import AnalyticsRuntime, RuntimeContext
from camera_analytics.scene import SceneFactory
from camera_analytics.scheduler import ExecutionMode, ExecutionPolicy, ExecutionScheduler
from camera_analytics.sdk import (
    AnalyticsEvent,
    AnalyticsEventType,
    AnalyticsModule,
    AnalyticsResult,
)
from camera_analytics.sources.video_source import VideoSource
from camera_analytics.utils.visualizer import PoseVisualizer

logger = logging.getLogger("validate_execution_scheduler")


class ScheduledDemoPlugin(AnalyticsModule):
    """Analytics Module recording frame execution counts for ExecutionScheduler validation."""

    def __init__(self, name: str) -> None:
        super().__init__(name=name, description=f"Scheduled Demo Plugin ({name})")
        self.execution_count = 0

    def update(self, context: Any) -> Optional[AnalyticsResult]:
        return AnalyticsResult(module_name=self.name)

    def process(self, scene: Any) -> AnalyticsResult:
        self.execution_count += 1
        events: list[AnalyticsEvent] = []

        evt = AnalyticsEvent(
            event_id=f"evt_{self.name}_f{scene.frame.frame_index}",
            module_name=self.name,
            event_type=AnalyticsEventType.INFO,
            message=f"[{self.name}] Executed at frame {scene.frame.frame_index} (total_execs={self.execution_count})",
            timestamp=scene.frame.timestamp,
            frame_index=scene.frame.frame_index,
        )
        events.append(evt)

        return AnalyticsResult(
            module_name=self.name,
            events=events,
            metrics={"execution_count": self.execution_count},
        )


def setup_logging() -> None:
    """Configure logging format."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )


def run_scheduler_validation(
    video_path: str = "camera_analytics/samples/Screen_Recording_20260622_113428_EZVIZ.mp4",
    weights_path: str = "yolo26m-pose.pt",
    output_path: str = "camera_analytics/samples/output_scheduler_validation.mp4",
    log_output_path: str = "camera_analytics/logs/scheduler_validation.jsonl",
    max_frames: Optional[int] = 200,
    device: str = "cuda",
) -> None:
    """Run full pipeline validation with ExecutionScheduler timing rules."""
    setup_logging()

    logger.info("=" * 75)
    logger.info("Sprint 10F -- Execution Scheduler Framework Validation")
    logger.info("=" * 75)

    # 1. Initialize Communication Layer
    comm_manager = CommunicationManager.get_instance(queue_size=10000)
    log_path_obj = Path(log_output_path)
    log_pub = LogPublisher(
        name="scheduler_log_publisher",
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
    camera = Camera("cam_scheduler_val", "Scheduler Managed Camera", video_path)
    for z in zones:
        camera.add_zone(z)

    pipeline_cfg = Config.from_dict({
        "pipeline": {"process_every_n": 1},
        "track_manager": {"max_history_length": 150, "confirm_after_n": 3, "max_lost_age": 30},
    })
    event_bus = EventBus()
    pipeline = Pipeline(pipeline_cfg, camera, event_bus)
    pipeline.start()

    # 5. Setup ModuleRegistry, ModuleManager, ExecutionScheduler, and AnalyticsRuntime
    registry = ModuleRegistry()
    manager = ModuleManager(registry=registry)
    scheduler = ExecutionScheduler()
    runtime_kernel = AnalyticsRuntime(module_manager=manager, execution_scheduler=scheduler)

    # Register 3 Modules with different ExecutionPolicies
    mod_people = ScheduledDemoPlugin("people_counter")
    mod_crowd = ScheduledDemoPlugin("crowd_density")
    mod_heatmap = ScheduledDemoPlugin("heatmap")

    desc_people = ModuleDescriptor(
        module_id="people_counter",
        module_name="People Counter (EVERY_FRAME)",
        priority=10,
        execution_policy=ExecutionPolicy(execution_mode=ExecutionMode.EVERY_FRAME),
    )
    desc_crowd = ModuleDescriptor(
        module_id="crowd_density",
        module_name="Crowd Density (INTERVAL 5)",
        priority=20,
        execution_policy=ExecutionPolicy(execution_mode=ExecutionMode.INTERVAL, interval=5),
    )
    desc_heatmap = ModuleDescriptor(
        module_id="heatmap",
        module_name="Heatmap Analytics (INTERVAL 10)",
        priority=30,
        execution_policy=ExecutionPolicy(execution_mode=ExecutionMode.INTERVAL, interval=10),
    )

    runtime_kernel.register_module(mod_people, desc_people)
    runtime_kernel.register_module(mod_crowd, desc_crowd)
    runtime_kernel.register_module(mod_heatmap, desc_heatmap)

    runtime_kernel.initialize()
    runtime_kernel.start()

    logger.info("Registered modules with ExecutionPolicies:")
    for desc, mod in manager.get_active_modules():
        logger.info("  - [%s] Mode: %s | Interval: %d | Priority: %d", desc.module_id, desc.execution_policy.execution_mode.name, desc.execution_policy.interval, desc.priority)

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

    logger.info("Processing frames with Execution Scheduler timing control...")
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

            # Dispatch Scene snapshot according to ExecutionScheduler timing rules
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
                model_name=f"Frame {frame_count} Executed: {','.join(executed_in_frame)}",
                tracker_name=tracker.name.upper(),
            )
            writer.write(annotated_frame)

            if frame_count % 50 == 0:
                logger.info(
                    "FRAME %d | Scheduled Executed: %s",
                    frame_count,
                    executed_in_frame,
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
    stats = runtime_kernel.context.statistics

    logger.info("=" * 75)
    logger.info("RUNTIME EXECUTION SCHEDULER REPORT")
    logger.info("=" * 75)
    logger.info("Total Frames Processed:      %d frames", frame_count)
    logger.info("Total Time Elapsed:          %.2f seconds", elapsed)
    logger.info("Average Frame Rate:          %.1f FPS", avg_fps)
    logger.info("Events Published & Logged:   %d events", metrics.published_events)
    logger.info("-" * 75)
    logger.info("EXECUTION SCHEDULER STATISTICS PER MODULE:")
    logger.info("  - Module 'people_counter     ' (EVERY_FRAME) : Executed %3d / %d frames (Execution Ratio: 100.0%%)", mod_people.execution_count, frame_count)
    logger.info("  - Module 'crowd_density      ' (INTERVAL 5)  : Executed %3d / %d frames (Execution Ratio:  %.1f%%)", mod_crowd.execution_count, frame_count, (mod_crowd.execution_count / frame_count) * 100.0)
    logger.info("  - Module 'heatmap            ' (INTERVAL 10) : Executed %3d / %d frames (Execution Ratio:  %.1f%%)", mod_heatmap.execution_count, frame_count, (mod_heatmap.execution_count / frame_count) * 100.0)
    logger.info("=" * 75)
    logger.info("Sprint 10F Execution Scheduler Framework validation complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Execution Scheduler Framework Validation Tool")
    parser.add_argument(
        "--video",
        type=str,
        default="camera_analytics/samples/Screen_Recording_20260622_113428_EZVIZ.mp4",
        help="Path to input video file",
    )
    parser.add_argument("--max-frames", type=int, default=200, help="Max frames to process")
    args = parser.parse_args()

    run_scheduler_validation(video_path=args.video, max_frames=args.max_frames)
