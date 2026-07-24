"""
Dynamic Plugin Loader Framework Validation Tool (Sprint 10H).

Creates sample python plugin modules and manifest files, executes PluginDiscovery and PluginLoader,
registers loaded AnalyticsModules into AnalyticsRuntime Kernel, processes 200 video frames,
and prints official Runtime Dynamic Plugin Loader Report.

Usage::

    python -m camera_analytics.tools.validate_dynamic_plugin_loader
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
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
from camera_analytics.runtime import AnalyticsRuntime
from camera_analytics.scene import SceneFactory
from camera_analytics.sdk import (
    AnalyticsEvent,
    AnalyticsEventType,
    AnalyticsModule,
    AnalyticsResult,
)
from camera_analytics.sources.video_source import VideoSource
from camera_analytics.utils.visualizer import PoseVisualizer

logger = logging.getLogger("validate_dynamic_plugin_loader")


# Sample Plugin Code Content for Dynamic Import Testing
PEOPLE_COUNTER_CODE = """
from camera_analytics.sdk import AnalyticsModule, AnalyticsResult, AnalyticsEvent, AnalyticsEventType

class PeopleCounterDynamicPlugin(AnalyticsModule):
    def __init__(self, name: str = "people_counter") -> None:
        super().__init__(name=name, description="Dynamic People Counter Plugin")
        self.count = 0

    def update(self, context) -> AnalyticsResult:
        return AnalyticsResult(module_name=self.name)

    def process(self, scene) -> AnalyticsResult:
        self.count = len(scene.tracks)
        events = []
        if scene.frame.frame_index % 30 == 0:
            events.append(AnalyticsEvent(
                event_id=f"evt_pc_{scene.frame.frame_index}",
                module_name=self.name,
                event_type=AnalyticsEventType.INFO,
                message=f"[PeopleCounterDynamicPlugin] Count: {self.count} people active",
                timestamp=scene.frame.timestamp,
                frame_index=scene.frame.frame_index,
            ))
        return AnalyticsResult(module_name=self.name, events=events, metrics={"people_count": self.count})
"""

DWELL_TIME_CODE = """
from camera_analytics.sdk import AnalyticsModule, AnalyticsResult, AnalyticsEvent, AnalyticsEventType

class DwellTimeDynamicPlugin(AnalyticsModule):
    def __init__(self, name: str = "dwell_time") -> None:
        super().__init__(name=name, description="Dynamic Dwell Time Plugin")

    def update(self, context) -> AnalyticsResult:
        return AnalyticsResult(module_name=self.name)

    def process(self, scene) -> AnalyticsResult:
        events = []
        if scene.frame.frame_index % 50 == 0:
            events.append(AnalyticsEvent(
                event_id=f"evt_dt_{scene.frame.frame_index}",
                module_name=self.name,
                event_type=AnalyticsEventType.INFO,
                message=f"[DwellTimeDynamicPlugin] Evaluating dwell times for {len(scene.tracks)} tracks",
                timestamp=scene.frame.timestamp,
                frame_index=scene.frame.frame_index,
            ))
        return AnalyticsResult(module_name=self.name, events=events)
"""

INVALID_TYPE_CODE = """
class NonModuleDynamicClass:
    def __init__(self) -> None:
        pass
"""


def setup_logging() -> None:
    """Configure logging format."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )


def create_dynamic_plugin_files(base_dir: Path) -> None:
    """Create Python module files and manifest.json files for dynamic loading tests.

    Args:
        base_dir: Root directory path for plugins (e.g. 'camera_analytics/plugins').
    """
    if base_dir.exists():
        shutil.rmtree(base_dir, ignore_errors=True)
    base_dir.mkdir(parents=True, exist_ok=True)

    # 1. Valid Plugin: People Counter
    p1 = base_dir / "people_counter"
    p1.mkdir(exist_ok=True)
    with open(p1 / "module.py", "w", encoding="utf-8") as f:
        f.write(PEOPLE_COUNTER_CODE)
    with open(p1 / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "plugin_id": "people_counter",
                "name": "People Counter Dynamic",
                "version": "1.0.0",
                "sdk_version": "1.0.0",
                "entry_point": "camera_analytics.plugins.people_counter.module.PeopleCounterDynamicPlugin",
                "capabilities": ["TRACKING", "POSE", "ZONE"],
                "execution_policy": {"execution_mode": "EVERY_FRAME", "interval": 1},
                "priority": 10,
            },
            f,
            indent=2,
        )

    # 2. Valid Plugin: Dwell Time
    p2 = base_dir / "dwell_time"
    p2.mkdir(exist_ok=True)
    with open(p2 / "module.py", "w", encoding="utf-8") as f:
        f.write(DWELL_TIME_CODE)
    with open(p2 / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "plugin_id": "dwell_time",
                "name": "Dwell Time Dynamic",
                "version": "1.0.0",
                "sdk_version": "1.0.0",
                "entry_point": "camera_analytics.plugins.dwell_time.module.DwellTimeDynamicPlugin",
                "capabilities": ["TRACKING", "ZONE", "GROUND_POINT"],
                "execution_policy": {"execution_mode": "INTERVAL", "interval": 5},
                "priority": 20,
            },
            f,
            indent=2,
        )

    # 3. Invalid Plugin: ImportError (Non-existent python module)
    p3 = base_dir / "broken_import"
    p3.mkdir(exist_ok=True)
    with open(p3 / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "plugin_id": "broken_import_mod",
                "name": "Broken Import Module",
                "version": "1.0.0",
                "sdk_version": "1.0.0",
                "entry_point": "camera_analytics.plugins.non_existent_pkg.FakeModule",
            },
            f,
            indent=2,
        )

    # 4. Invalid Plugin: InvalidType (Class does not inherit from AnalyticsModule)
    p4 = base_dir / "invalid_type"
    p4.mkdir(exist_ok=True)
    with open(p4 / "module.py", "w", encoding="utf-8") as f:
        f.write(INVALID_TYPE_CODE)
    with open(p4 / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "plugin_id": "invalid_type_mod",
                "name": "Invalid Type Module",
                "version": "1.0.0",
                "sdk_version": "1.0.0",
                "entry_point": "camera_analytics.plugins.invalid_type.module.NonModuleDynamicClass",
            },
            f,
            indent=2,
        )


def run_loader_validation(
    video_path: str = "camera_analytics/samples/Screen_Recording_20260622_113428_EZVIZ.mp4",
    weights_path: str = "yolo26m-pose.pt",
    output_path: str = "camera_analytics/samples/output_loader_validation.mp4",
    log_output_path: str = "camera_analytics/logs/loader_validation.jsonl",
    plugins_dir: str = "camera_analytics/plugins",
    max_frames: Optional[int] = 200,
    device: str = "cuda",
) -> None:
    """Run full pipeline validation with Dynamic Plugin Loader."""
    setup_logging()

    logger.info("=" * 75)
    logger.info("Sprint 10H -- Dynamic Plugin Loader Framework Validation")
    logger.info("=" * 75)

    base_path = Path(plugins_dir)
    logger.info("Creating dynamic plugin Python modules and manifests at '%s'...", base_path)
    create_dynamic_plugin_files(base_path)

    # 1. Initialize Communication Layer
    comm_manager = CommunicationManager.get_instance(queue_size=10000)
    log_path_obj = Path(log_output_path)
    log_pub = LogPublisher(
        name="loader_log_publisher",
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
    camera = Camera("cam_loader_val", "Dynamic Plugin Camera", video_path)
    for z in zones:
        camera.add_zone(z)

    pipeline_cfg = Config.from_dict({
        "pipeline": {"process_every_n": 1},
        "track_manager": {"max_history_length": 150, "confirm_after_n": 3, "max_lost_age": 30},
    })
    event_bus = EventBus()
    pipeline = Pipeline(pipeline_cfg, camera, event_bus)
    pipeline.start()

    # 5. Setup AnalyticsRuntime Kernel and Dynamically Load Plugins
    runtime_kernel = AnalyticsRuntime()

    logger.info("Executing PluginDiscovery and PluginLoader from directory '%s'...", base_path)
    loading_report = runtime_kernel.load_plugins_from_directory(base_path)

    # Run initialize & start kernel
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

    logger.info("Processing frames with Dynamically Loaded Analytics Modules...")
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

            # Dispatch Scene snapshot to dynamically loaded modules
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
                model_name=f"Dynamic Modules: {','.join(executed_in_frame)}",
                tracker_name=tracker.name.upper(),
            )
            writer.write(annotated_frame)

            if frame_count % 50 == 0:
                logger.info(
                    "FRAME %d | Executing Dynamically Loaded Modules: %s",
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
    report_dict = loading_report.to_dict()

    logger.info("=" * 75)
    logger.info("RUNTIME DYNAMIC PLUGIN LOADER REPORT")
    logger.info("=" * 75)
    logger.info("Total Frames Processed:      %d frames", frame_count)
    logger.info("Total Time Elapsed:          %.2f seconds", elapsed)
    logger.info("Average Frame Rate:          %.1f FPS", avg_fps)
    logger.info("Events Published & Logged:   %d events", metrics.published_events)
    logger.info("-" * 75)
    logger.info("DYNAMIC LOADING SUMMARY:")
    logger.info("  - Evaluated Manifests:    %d", report_dict["found_count"])
    logger.info("  - Successfully Loaded:    %d module(s)", report_dict["loaded_count"])
    logger.info("  - Rejected Plugins:       %d module(s)", report_dict["rejected_count"])
    logger.info("    * ImportError:          %d", report_dict["breakdown"]["import_error"])
    logger.info("    * ClassNotFound:        %d", report_dict["breakdown"]["class_not_found"])
    logger.info("    * InvalidType:          %d", report_dict["breakdown"]["invalid_type"])
    logger.info("-" * 75)
    logger.info("SUCCESSFULLY LOADED PLUGINS:")
    for rec in loading_report.loaded_records:
        logger.info(
            "  - Module ID: '%-18s' | Class: %-25s | State: %s",
            rec.descriptor.module_id,
            rec.instance.__class__.__name__ if rec.instance else "N/A",
            rec.descriptor.state.name,
        )
    logger.info("-" * 75)
    logger.info("REJECTED PLUGINS (ISOLATED SAFELY WITHOUT CRASH):")
    for rec in loading_report.rejected_records:
        logger.info(
            "  - Module ID: '%-18s' | Status: %-15s | Error: %s",
            rec.descriptor.module_id,
            rec.status,
            rec.error_message,
        )
    logger.info("=" * 75)
    logger.info("Sprint 10H Dynamic Plugin Loader Framework validation complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dynamic Plugin Loader Framework Validation Tool")
    parser.add_argument(
        "--video",
        type=str,
        default="camera_analytics/samples/Screen_Recording_20260622_113428_EZVIZ.mp4",
        help="Path to input video file",
    )
    parser.add_argument("--max-frames", type=int, default=200, help="Max frames to process")
    args = parser.parse_args()

    run_loader_validation(video_path=args.video, max_frames=args.max_frames)
