"""
Centralized Configuration Layer package.

Exports strongly-typed, immutable configuration schemas and the ConfigLoader:
    - AppConfig, CameraConfig, SourceConfig, DetectorConfig, TrackerConfig, RunnerConfig, AnalyticsConfig
    - ConfigLoader, ConfigValidationError
"""

from camera_analytics.config.loader import ConfigLoader, ConfigValidationError
from camera_analytics.config.schema import (
    AnalyticsConfig,
    AppConfig,
    CameraConfig,
    DetectorConfig,
    RunnerConfig,
    SourceConfig,
    TrackerConfig,
)

__all__ = [
    # Root & Subsystem Schemas
    "AppConfig",
    "CameraConfig",
    "SourceConfig",
    "DetectorConfig",
    "TrackerConfig",
    "RunnerConfig",
    "AnalyticsConfig",
    # Loader & Validation Exception
    "ConfigLoader",
    "ConfigValidationError",
]
