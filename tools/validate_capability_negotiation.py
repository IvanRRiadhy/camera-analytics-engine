"""
Capability Negotiation Framework Validation Tool (Sprint 10E).

Executes real video pipeline with 4 registered Analytics Modules testing supported vs unsupported capabilities.

Validates:
    - 2 Supported Modules ('people_counter', 'dwell_time') executing normally.
    - 2 Unsupported Modules ('alpr_vehicle_reid', '3d_depth_analytics') marked UNSUPPORTED and skipped cleanly.
    - CapabilityValidationReport generation summarizing runtime capabilities, supported modules, and missing capabilities.
    - Event publishing to JSON Lines (.jsonl) log file (`camera_analytics/logs/capability_validation.jsonl`).

Usage::

    python -m camera_analytics.tools.validate_capability_negotiation
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
from camera_analytics.capability import (
    Capability,
    CapabilityNegotiator,
    CapabilitySet,
    RuntimeCapabilityProvider,
)
from camera_analytics.communication import CommunicationManager, LogPublisher
from camera_analytics.core import Config, EventBus, Pipeline
from camera_analytics.core.zone_engine import ZoneEngine
from camera_analytics.entities import AnalyticsPayload, EntitySerializer
from camera_analytics.models import Camera, Point, Zone, ZoneType
from camera_analytics.registry import ModuleDescriptor, ModuleManager, ModuleRegistry, ModuleState
from camera_analytics.runtime import AnalyticsRuntime, RuntimeContext
from camera_analytics.scene import SceneFactory
from camera_analytics.sdk import (
    AnalyticsEvent,
    AnalyticsEventType,
    AnalyticsModule,
    AnalyticsResult,
)
from camera_analytics.sources.video_source import VideoSource
from camera_analytics.utils.visualizer import PoseVisualizer

logger = logging.getLogger("validate_capability_negotiation")


class CapabilityDemoPlugin(AnalyticsModule):
    """Analytics Module with declared capabilities for negotiation validation."""

    def __init__(self, name: str, capabilities: list[str]) -> None:
        super().__init__(name=name, description=f"Capability Demo Plugin ({name})")
        self.declared_capabilities = capabilities
        self.processed_frames = 0

    def update(self, context: Any) -> Optional[AnalyticsResult]:
        return AnalyticsResult(module_name=self.name)

    def process(self, scene: Any) -> AnalyticsResult:
        self.processed_frames += 1
        events: list[AnalyticsEvent] = []

        if scene.frame.frame_index % 30 == 0:
            evt = AnalyticsEvent(
                event_id=f"evt_{self.name}_f{scene.frame.frame_index}",
                module_name=self.name,
                event_type=AnalyticsEventType.INFO,
                message=f"[{self.name}] Active at frame {scene.frame.frame_index} (capabilities={self.declared_capabilities})",
                timestamp=scene.frame.timestamp,
                frame_index=scene.frame.frame_index,
            )
            events.append(evt)

        return AnalyticsResult(
            module_name=self.name,
            events=events,
            metrics={"processed_frames": self.processed_frames},
        )


def setup_logging() -> None:
    """Configure logging format."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )


def run_capability_validation(
    video_path: str = "camera_analytics/samples/Screen_Recording_20260622_113428_EZVIZ.mp4",
    weights_path: str = "yolo26m-pose.pt",
    output_path: str = "camera_analytics/samples/output_capability_validation.mp4",
    log_output_path: str = "camera_analytics/logs/capability_validation.jsonl",
    max_frames: Optional[int] = 200,
    device: str = "cuda",
) -> None:
    """Run full pipeline validation with Capability Negotiation Framework."""
    setup_logging()

    logger.info("=" * 75)
    logger.info("Sprint 10E -- Capability Negotiation Framework Validation")
    logger.info("=" * 75)

    # 1. Initialize Communication Layer
    comm_manager = CommunicationManager.get_instance(queue_size=10000)
    log_path_obj = Path(log_output_path)
    log_pub = LogPublisher(
        name="capability_log_publisher",
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
    camera = Camera("cam_capability_val", "Capability Negotiated Camera", video_path)
    for z in zones:
        camera.add_zone(z)

    pipeline_cfg = Config.from_dict({
        "pipeline": {"process_every_n": 1},
        "track_manager": {"max_history_length": 150, "confirm_after_n": 3, "max_lost_age": 30},
    })
    event_bus = EventBus()
    pipeline = Pipeline(pipeline_cfg, camera, event_bus)
    pipeline.start()

    # 5. Setup Runtime CapabilityProvider, Negotiator, and AnalyticsRuntime
    capability_provider = RuntimeCapabilityProvider(
        static_capabilities=["TRACKING", "POSE", "GROUND_POINT", "ZONE", "KEYPOINTS"]
    )
    negotiator = CapabilityNegotiator(provider=capability_provider)
    registry = ModuleRegistry()
    manager = ModuleManager(registry=registry)
    runtime_kernel = AnalyticsRuntime(module_manager=manager, capability_negotiator=negotiator)

    # Register 2 Supported Modules and 2 Unsupported Modules
    mod_people = CapabilityDemoPlugin("people_counter", ["TRACKING", "POSE", "ZONE"])
    mod_dwell = CapabilityDemoPlugin("dwell_time", ["TRACKING", "ZONE", "GROUND_POINT"])
    mod_reid = CapabilityDemoPlugin("alpr_vehicle_reid", ["REID", "CLASSIFICATION"])
    mod_depth = CapabilityDemoPlugin("3d_depth_analytics", ["DEPTH", "SEGMENTATION"])

    desc_people = ModuleDescriptor(
        module_id="people_counter",
        module_name="People Counter",
        capabilities=["TRACKING", "POSE", "ZONE"],
        priority=10,
    )
    desc_dwell = ModuleDescriptor(
        module_id="dwell_time",
        module_name="Dwell Time Analytics",
        capabilities=["TRACKING", "ZONE", "GROUND_POINT"],
        priority=20,
    )
    desc_reid = ModuleDescriptor(
        module_id="alpr_vehicle_reid",
        module_name="ALPR Vehicle ReID",
        capabilities=["REID", "CLASSIFICATION"],
        priority=30,
    )
    desc_depth = ModuleDescriptor(
        module_id="3d_depth_analytics",
        module_name="3D Depth Analytics",
        capabilities=["DEPTH", "SEGMENTATION"],
        priority=40,
    )

    runtime_kernel.register_module(mod_people, desc_people)
    runtime_kernel.register_module(mod_dwell, desc_dwell)
    runtime_kernel.register_module(mod_reid, desc_reid)
    runtime_kernel.register_module(mod_depth, desc_depth)

    # Run initialize -> triggers capability negotiation
    runtime_kernel.initialize()
    runtime_kernel.start()

    cap_report = runtime_kernel.get_capability_report()

    logger.info("Capability Negotiation Report:")
    logger.info("  - Platform Capabilities: %s", cap_report.runtime_capabilities.to_list())
    logger.info("  - Supported Modules:     %s", cap_report.supported_modules)
    logger.info("  - Unsupported Modules:   %s", cap_report.unsupported_modules)

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

    logger.info("Processing frames with Capability Negotiation Framework...")
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

            # Dispatch Scene snapshot (Unsupported modules automatically skipped)
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
            active_mod_names = [d.module_id for d, _ in manager.get_active_modules()]
            annotated_frame = visualizer.draw_tracks(
                frame=frame,
                tracks=active_tracks,
                zones=zones,
                track_zone_states=zone_result.track_states,
                frame_id=frame_count,
                fps=fps,
                device=f"CUDA ({detector.name})",
                model_name=f"Supported: {','.join(active_mod_names)}",
                tracker_name=tracker.name.upper(),
            )
            writer.write(annotated_frame)

            if frame_count % 50 == 0:
                logger.info(
                    "FRAME %d | Supported Executing: %d | Unsupported Skipped: %d",
                    frame_count,
                    len(cap_report.supported_modules),
                    len(cap_report.unsupported_modules),
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
    report_dict = cap_report.to_dict()

    logger.info("=" * 75)
    logger.info("RUNTIME CAPABILITY VALIDATION REPORT")
    logger.info("=" * 75)
    logger.info("Total Frames Processed:      %d frames", frame_count)
    logger.info("Total Time Elapsed:          %.2f seconds", elapsed)
    logger.info("Average Frame Rate:          %.1f FPS", avg_fps)
    logger.info("Events Published & Logged:   %d events", metrics.published_events)
    logger.info("-" * 75)
    logger.info("PLATFORM CAPABILITY SUMMARY:")
    logger.info("  - Active Capabilities:    %s", report_dict["runtime_capability_summary"])
    logger.info("-" * 75)
    logger.info("SUPPORTED MODULES (%d):", report_dict["supported_modules_count"])
    for mod_id in report_dict["supported_modules"]:
        desc = registry.get_descriptor(mod_id)
        logger.info("  - Module ID: '%-20s' | State: %-12s | Capabilities: %s", mod_id, desc.state.name if desc else "N/A", desc.capabilities if desc else [])
    logger.info("-" * 75)
    logger.info("UNSUPPORTED MODULES (%d - SKIPPED CLEANLY WITHOUT ERROR):", report_dict["unsupported_modules_count"])
    for mod_id in report_dict["unsupported_modules"]:
        desc = registry.get_descriptor(mod_id)
        missing_caps = report_dict["missing_capabilities"].get(mod_id, [])
        logger.info("  - Module ID: '%-20s' | State: %-12s | Missing Caps: %s", mod_id, desc.state.name if desc else "N/A", missing_caps)
    logger.info("=" * 75)
    logger.info("Sprint 10E Capability Negotiation Framework validation complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Capability Negotiation Framework Validation Tool")
    parser.add_argument(
        "--video",
        type=str,
        default="camera_analytics/samples/Screen_Recording_20260622_113428_EZVIZ.mp4",
        help="Path to input video file",
    )
    parser.add_argument("--max-frames", type=int, default=200, help="Max frames to process")
    args = parser.parse_args()

    run_capability_validation(video_path=args.video, max_frames=args.max_frames)
