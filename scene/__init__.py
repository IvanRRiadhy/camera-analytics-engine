"""
Scene Layer Package.

Provides immutable Scene snapshots, SceneMetadata, SceneStatistics, SceneBuilder, and SceneFactory.
Establishes the primary domain contract between Vision Runtime and Analytics Runtime.
"""

from camera_analytics.scene.builder import SceneBuilder
from camera_analytics.scene.factory import SceneFactory
from camera_analytics.scene.models import (
    Scene,
    SceneMetadata,
    SceneStatistics,
)

__all__ = [
    "Scene",
    "SceneMetadata",
    "SceneStatistics",
    "SceneBuilder",
    "SceneFactory",
]
