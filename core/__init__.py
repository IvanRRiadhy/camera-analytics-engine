"""
Core framework package.

Exports the primary building blocks of the camera analytics framework:
Pipeline, AnalyticsModule, EventBus, Config, FrameContext, TrackManager,
RuntimeState, DetectionSet, Ports, FrameSource, and Runner.

Usage::

    from camera_analytics.core import Pipeline, Config, AnalyticsModule, Runner, FrameSource
    from camera_analytics.core import FrameContext, TrackManager, DetectionSet
"""

from camera_analytics.core.base_module import (
    AnalyticsModule,
    ModuleInfo,
    ModuleLifecycle,
    ModuleOutput,
)
from camera_analytics.core.config import Config, ConfigError, ModuleConfig
from camera_analytics.core.detection_set import DetectionSet
from camera_analytics.core.events import EventBus
from camera_analytics.core.frame_context import FrameContext, build_frame_context
from camera_analytics.core.frame_source import FakeFrameSource, FrameSource
from camera_analytics.core.pipeline import Pipeline, PipelineState, PipelineStats
from camera_analytics.core.ports import (
    DetectionResult,
    DetectorPort,
    TrackerPort,
    TrackingResult,
)
from camera_analytics.core.registry import ModuleRegistry, RegistryError
from camera_analytics.core.runner import Runner
from camera_analytics.core.runtime import RuntimeState
from camera_analytics.core.track_features import TrackFeatureStore
from camera_analytics.core.track_manager import TrackManager, TrackerResult

__all__ = [
    # Pipeline
    "Pipeline",
    "PipelineState",
    "PipelineStats",
    # Runner & FrameSource
    "Runner",
    "FrameSource",
    "FakeFrameSource",
    # Module
    "AnalyticsModule",
    "ModuleInfo",
    "ModuleLifecycle",
    "ModuleOutput",
    # Config
    "Config",
    "ConfigError",
    "ModuleConfig",
    # Events
    "EventBus",
    # FrameContext
    "FrameContext",
    "build_frame_context",
    # Detection
    "DetectionSet",
    # Track Management
    "TrackManager",
    "TrackerResult",
    "TrackFeatureStore",
    # Runtime
    "RuntimeState",
    # Ports (AI Model Interfaces)
    "DetectorPort",
    "TrackerPort",
    "DetectionResult",
    "TrackingResult",
    # Registry
    "ModuleRegistry",
    "RegistryError",
]
