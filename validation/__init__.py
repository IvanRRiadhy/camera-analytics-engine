"""
Enterprise Analytics Validation Framework Package.

Provides dataset management, ground truth schemas, runtime replay engine, event comparator,
metrics engine, baseline quality gates, and report generation tools.
"""

from camera_analytics.validation.baseline import (
    BaselineComparisonError,
    BaselineManager,
    ValidationHistoryStore,
)
from camera_analytics.validation.comparator import EventComparator
from camera_analytics.validation.dataset import (
    ValidationDataset,
    ValidationDatasetManager,
)
from camera_analytics.validation.metrics import AnalyticsMetricsEngine
from camera_analytics.validation.replay import RuntimeReplayEngine
from camera_analytics.validation.report import ValidationReportGenerator
from camera_analytics.validation.schema import (
    AnalyticsModuleMetrics,
    CameraFeedConfig,
    DatasetManifest,
    EventMatchResult,
    GroundTruthEvent,
    MatchStatus,
    SystemResourceMetrics,
    ValidationTolerance,
)

__all__ = [
    "DatasetManifest",
    "CameraFeedConfig",
    "GroundTruthEvent",
    "ValidationTolerance",
    "MatchStatus",
    "EventMatchResult",
    "SystemResourceMetrics",
    "AnalyticsModuleMetrics",
    "ValidationDataset",
    "ValidationDatasetManager",
    "RuntimeReplayEngine",
    "EventComparator",
    "AnalyticsMetricsEngine",
    "BaselineManager",
    "BaselineComparisonError",
    "ValidationHistoryStore",
    "ValidationReportGenerator",
]
