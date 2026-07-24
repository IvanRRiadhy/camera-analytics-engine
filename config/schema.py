"""
Configuration schemas for the camera analytics platform.

Defines strongly-typed, immutable dataclass schemas for each subsystem:
    - CameraConfig: Camera identity, resolution, FPS, and zones.
    - SourceConfig: Frame source type, URI, and source parameters.
    - DetectorConfig: Object detector model, weights, device, and thresholds.
    - TrackerConfig: Object tracking algorithm and matching parameters.
    - RunnerConfig: Execution loop parameters (skipping, frame limits).
    - AnalyticsConfig: Active analytics modules and module-specific settings.
    - AppConfig: Root configuration combining all subsystem configurations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from camera_analytics.models.zone import Zone


@dataclass(frozen=True, slots=True)
class CameraConfig:
    """Configuration for camera hardware/identity.

    Attributes:
        camera_id: Unique identifier for the camera.
        name: Human-readable camera name.
        resolution: Camera frame size tuple (width, height).
        fps: Camera frame rate.
        zones: Tuple of Zone objects defined for this camera.
    """

    camera_id: str
    name: str = ""
    resolution: tuple[int, int] = (1920, 1080)
    fps: float = 30.0
    zones: tuple[Zone, ...] = ()


@dataclass(frozen=True, slots=True)
class SourceConfig:
    """Configuration for frame source stream/input.

    Attributes:
        source_type: Type of source ('video', 'rtsp', 'usb', 'folder').
        uri: Resource URI (file path, RTSP URL, device index string, or folder path).
        params: Additional source-specific parameters (e.g. reconnect_delay).
    """

    source_type: str
    uri: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DetectorConfig:
    """Configuration for object detection model adapter.

    Attributes:
        model_name: Detector implementation identifier (e.g. 'yolo_pose', 'fake_detector').
        model_path: Path to model weights file.
        device: Compute device ('cuda', 'cpu', 'mps').
        confidence_threshold: Minimum detection confidence.
        iou_threshold: IoU threshold for NMS.
        extra_params: Additional detector parameters.
    """

    model_name: str = "fake_detector"
    model_path: str = ""
    device: str = "cpu"
    confidence_threshold: float = 0.5
    iou_threshold: float = 0.45
    extra_params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TrackerConfig:
    """Configuration for object tracking algorithm adapter.

    Attributes:
        tracker_name: Tracker implementation identifier (e.g. 'botsort', 'fake_tracker').
        max_distance: Maximum distance threshold for association matching.
        max_lost: Consecutive frames before dropping a lost track.
        extra_params: Additional tracker parameters.
    """

    tracker_name: str = "fake_tracker"
    max_distance: float = 150.0
    max_lost: int = 10
    extra_params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RunnerConfig:
    """Configuration for runner execution loop.

    Attributes:
        process_every_n: Process 1 frame every N frames (frame skipping).
        max_frames: Optional maximum frame limit to process before stopping.
    """

    process_every_n: int = 1
    max_frames: Optional[int] = None


@dataclass(frozen=True, slots=True)
class AnalyticsConfig:
    """Configuration for analytics modules and their settings.

    Attributes:
        enabled_modules: Tuple of module names to register and run.
        module_settings: Dictionary of module_name -> settings dict.
    """

    enabled_modules: tuple[str, ...] = ()
    module_settings: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Root configuration combining all subsystem configurations.

    Attributes:
        camera: Camera configuration.
        source: Frame source configuration.
        detector: Detector model configuration.
        tracker: Tracker algorithm configuration.
        runner: Runner execution configuration.
        analytics: Analytics modules configuration.
    """

    camera: CameraConfig
    source: SourceConfig
    detector: DetectorConfig
    tracker: TrackerConfig
    runner: RunnerConfig
    analytics: AnalyticsConfig
