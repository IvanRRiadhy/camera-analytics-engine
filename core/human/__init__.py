"""
Human Domain Package exports.
"""

from camera_analytics.core.human.base_module import BaseHumanAnalyticsModule, ModuleConfig
from camera_analytics.core.human.cache import HumanStateCache
from camera_analytics.core.human.dependency_graph import ModuleDependencyGraph, ModuleNode
from camera_analytics.core.human.model_manager import IInferenceBackend, ModelManager, StubInferenceBackend
from camera_analytics.core.human.models import (
    AppearanceState,
    BehaviorCuesState,
    DemographicsState,
    ExpressionState,
    HumanRepresentation,
    HumanState,
    IdentityState,
    PPEState,
    ROICropCache,
)
from camera_analytics.core.human.quality_estimator import FaceQualityEstimator
from camera_analytics.core.human.registry import InferenceModelRegistry, ModelMetadata
from camera_analytics.core.human.representation_extractor import HumanRepresentationExtractor
from camera_analytics.core.human.runtime import HumanRuntime, HumanRuntimeResult
from camera_analytics.core.human.scheduler import HumanAnalyticsScheduler, ModuleExecutionMetrics

__all__ = [
    "ROICropCache",
    "HumanRepresentation",
    "DemographicsState",
    "ExpressionState",
    "IdentityState",
    "PPEState",
    "AppearanceState",
    "BehaviorCuesState",
    "HumanState",
    "FaceQualityEstimator",
    "HumanRepresentationExtractor",
    "HumanStateCache",
    "ModelMetadata",
    "InferenceModelRegistry",
    "IInferenceBackend",
    "StubInferenceBackend",
    "ModelManager",
    "ModuleConfig",
    "BaseHumanAnalyticsModule",
    "ModuleNode",
    "ModuleDependencyGraph",
    "ModuleExecutionMetrics",
    "HumanAnalyticsScheduler",
    "HumanRuntime",
    "HumanRuntimeResult",
]
