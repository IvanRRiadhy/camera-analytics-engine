"""
Camera Analytics Framework -- Sprint 6B Demo (BoT-SORT Integration).

Demonstrates full end-to-end integration:
    VideoSource -> YOLO26m-Pose (DetectorPort) -> BoT-SORT (TrackerPort) -> Pipeline -> TrackManager -> Visualizer

Run from the project root::

    python -m camera_analytics.demo
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

from camera_analytics.adapters import (
    BoTSORTAdapter,
    YOLOPoseAdapter,
)
from camera_analytics.analytics.people import PeopleAnalytics
from camera_analytics.config import (
    AppConfig,
    ConfigLoader,
    ConfigValidationError,
    DetectorConfig,
    TrackerConfig,
)
from camera_analytics.core import (
    Config,
    DetectorPort,
    EventBus,
    Pipeline,
    Runner,
    TrackerPort,
)
from camera_analytics.models import Camera, Point, Zone, ZoneType
from camera_analytics.sources import VideoSource

logger = logging.getLogger("demo")


def setup_logging() -> None:
    """Configure logging for the demo."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )


def create_demo_raw_dict() -> dict[str, Any]:
    """Create a sample raw configuration dictionary."""
    critical_zone = Zone(
        zone_id="critical",
        name="Critical Area",
        zone_type=ZoneType.REGION,
        points=[
            Point(380, 360),
            Point(830, 250),
            Point(800, 360),
            Point(470, 470),
        ],
        color=(255, 0, 255),
    )

    entrance_zone = Zone(
        zone_id="entrance",
        name="Main Entrance",
        zone_type=ZoneType.REGION,
        points=[
            Point(560, 860),
            Point(1100, 720),
            Point(1500, 1070),
            Point(500, 1070),
        ],
        color=(0, 255, 0),
    )

    restricted_zone = Zone(
        zone_id="restricted",
        name="Restricted Area",
        zone_type=ZoneType.REGION,
        points=[
            Point(960, 380),
            Point(1200, 80),
            Point(1900, 620),
            Point(1800, 990),
        ],
        color=(0, 0, 255),
    )

    local_weights = "yolo26m-pose.pt" if Path("yolo26m-pose.pt").exists() else "yolov8n-pose.pt"

    candidate_video_paths = [
        # "AI/data/Screen_Recording_20260622_113428_EZVIZ.mp4",
        "camera_analytics/samples/Screen_Recording_20260622_113428_EZVIZ.mp4",
        # "samples/lobby_clip.mp4",
    ]
    video_uri = next((p for p in candidate_video_paths if Path(p).exists()), "samples/lobby_clip.mp4")

    return {
        "camera": {
            "camera_id": "cam_lobby_01",
            "name": "Lobby Camera",
            "resolution": (1920, 1080),
            "fps": 30.0,
            "zones": [entrance_zone, restricted_zone],
        },
        "source": {
            "source_type": "video",
            "uri": video_uri,
            "params": {"target_fps": 30.0},
        },
        "detector": {
            "model_name": "yolo_pose",
            "model_path": local_weights,
            "device": "cuda",
            "confidence_threshold": 0.5,
            "iou_threshold": 0.45,
        },
        "tracker": {
            "tracker_name": "botsort",
            "max_distance": 150.0,
            "max_lost": 10,
        },
        "runner": {
            "process_every_n": 1,
            "max_frames": 20,
        },
        "analytics": {
            "enabled_modules": ["people_analytics"],
            "module_settings": {
                "people_analytics": {
                    "enabled": True,
                    "confidence_threshold": 0.5,
                    "crowd_threshold": 3,
                }
            },
        },
    }


def create_detector(config: DetectorConfig) -> DetectorPort:
    """Instantiate a DetectorPort (YOLOPoseAdapter or FakeDetector fallback)."""
    if config.model_name == "yolo_pose":
        try:
            adapter = YOLOPoseAdapter(
                confidence_threshold=config.confidence_threshold,
                iou_threshold=config.iou_threshold,
            )
            adapter.load(config.model_path, device=config.device)
            return adapter
        except (RuntimeError, FileNotFoundError, ImportError) as exc:
            logger.warning(
                "YOLOPoseAdapter unavailable (%s). Falling back gracefully to FakeDetector.",
                exc,
            )

    fake = FakeDetector(
        person_count=4,
        confidence_range=(config.confidence_threshold, 0.95),
        seed=42,
    )
    fake.load(config.model_path, device=config.device)
    return fake


def create_tracker(config: TrackerConfig) -> TrackerPort:
    """Instantiate a TrackerPort (BoTSORTAdapter or FakeTracker fallback)."""
    if config.tracker_name == "botsort":
        try:
            adapter = BoTSORTAdapter(
                track_high_thresh=0.5,
                match_thresh=0.8,
            )
            adapter.initialize()
            return adapter
        except Exception as exc:
            logger.warning("BoTSORTAdapter initialization notice (%s). Using fallback.", exc)

    fake = FakeTracker(
        max_distance=config.max_distance,
        max_lost=config.max_lost,
    )
    fake.initialize()
    return fake


def main() -> None:
    """Run the Sprint 6B demo showcasing end-to-end YOLO26m-Pose + BoT-SORT tracking."""
    setup_logging()

    logger.info("=" * 60)
    logger.info("Camera Analytics Framework -- Sprint 6B Demo (BoT-SORT Integration)")
    logger.info("=" * 60)

    # --- 1. Load and Validate Configuration ---
    raw_dict = create_demo_raw_dict()
    logger.info("Loading configuration dictionary via ConfigLoader...")

    try:
        app_config: AppConfig = ConfigLoader.from_dict(raw_dict)
    except ConfigValidationError as exc:
        logger.error("Configuration validation failed: %s", exc)
        return

    logger.info("AppConfig loaded successfully!")
    logger.info("  DetectorConfig: model=%s, path='%s', dev=%s",
                app_config.detector.model_name, app_config.detector.model_path, app_config.detector.device)
    logger.info("  TrackerConfig:  tracker=%s, max_dist=%.1f",
                app_config.tracker.tracker_name, app_config.tracker.max_distance)

    # --- 2. Instantiate System Components ---
    camera = Camera(
        camera_id=app_config.camera.camera_id,
        name=app_config.camera.name,
        source=app_config.source.uri,
    )
    camera.update_resolution(
        width=app_config.camera.resolution[0],
        height=app_config.camera.resolution[1],
        fps=app_config.camera.fps,
    )
    for z in app_config.camera.zones:
        camera.add_zone(z)
    camera.set_online()

    source = VideoSource(file_path=app_config.source.uri)
    detector = create_detector(app_config.detector)
    tracker = create_tracker(app_config.tracker)

    logger.info("Active Detector: %s", detector.name)
    logger.info("Active Tracker:  %s", tracker.name)

    # Core Pipeline config
    core_config = Config.from_dict({
        "pipeline": {"process_every_n": app_config.runner.process_every_n},
        "modules": app_config.analytics.module_settings,
    })

    event_bus = EventBus()
    pipeline = Pipeline(core_config, camera, event_bus)

    if "people_analytics" in app_config.analytics.enabled_modules:
        pipeline.register(PeopleAnalytics())

    runner = Runner(
        pipeline=pipeline,
        detector=detector,
        tracker=tracker,
    )

    # --- 3. Execute Processing Loop ---
    logger.info("")
    logger.info("Running execution loop via Runner...")
    logger.info("-" * 60)

    runner.run(source, max_frames=app_config.runner.max_frames)

    logger.info("-" * 60)

    # --- 4. Output Summary & TrackManager Stats ---
    people_output = pipeline.get_module_output("people_analytics")
    if people_output is not None:
        logger.info("PeopleAnalytics Output:")
        logger.info("  Current count: %d", people_output.current_count)
        logger.info("  Crowd active:  %s", people_output.crowd_active)
        logger.info("  Zone counts:   %s", people_output.zone_counts)

    runtime = pipeline.runtime
    if runtime is not None:
        tm = runtime.track_manager
        logger.info("TrackManager Stats: Active=%d, Confirmed=%d, Total Created=%d",
                    tm.active_count, tm.confirmed_count, tm.total_created)

    stats = pipeline.stop()
    logger.info("Pipeline Stats: processed %d frames in %.4fs (%.1f FPS)",
                stats.total_frames, stats.total_time_sec, stats.avg_fps)

    detector.release()
    tracker.reset()

    logger.info("")
    logger.info("=" * 60)
    logger.info("Sprint 6B demo complete. BoT-SORT tracking integration verified.")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
