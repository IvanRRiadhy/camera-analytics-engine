"""
Runtime Context Component.

Provides a thread-safe execution context, dependency container, and runtime performance statistics
for the Analytics Runtime Kernel.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Optional

from camera_analytics.entities.models import CameraEntity


@dataclass(slots=True)
class RuntimeStatistics:
    """Performance and execution statistics for the Analytics Runtime Kernel.

    Attributes:
        total_processed_scenes: Total number of Scene snapshots processed by the kernel.
        total_events_emitted: Total number of AnalyticsEvent objects generated across all plugins.
        total_execution_time_ms: Accumulated execution duration in milliseconds.
        plugin_execution_counts: Dictionary mapping module_name -> total execution count.
        plugin_error_counts: Dictionary mapping module_name -> total error count.
    """

    total_processed_scenes: int = 0
    total_events_emitted: int = 0
    total_execution_time_ms: float = 0.0
    plugin_execution_counts: dict[str, int] = field(default_factory=dict)
    plugin_error_counts: dict[str, int] = field(default_factory=dict)

    @property
    def average_execution_time_ms(self) -> float:
        """Calculate average processing time per scene in milliseconds."""
        if self.total_processed_scenes == 0:
            return 0.0
        return self.total_execution_time_ms / self.total_processed_scenes

    def record_scene_execution(
        self,
        execution_time_ms: float,
        events_count: int,
        executed_modules: list[str],
        error_modules: list[str],
    ) -> None:
        """Record statistics for a processed Scene iteration.

        Args:
            execution_time_ms: Frame execution duration in milliseconds.
            events_count: Number of events emitted in this frame.
            executed_modules: List of module names that executed successfully.
            error_modules: List of module names that experienced an exception.
        """
        self.total_processed_scenes += 1
        self.total_execution_time_ms += execution_time_ms
        self.total_events_emitted += events_count

        for mod_name in executed_modules:
            self.plugin_execution_counts[mod_name] = self.plugin_execution_counts.get(mod_name, 0) + 1

        for mod_name in error_modules:
            self.plugin_error_counts[mod_name] = self.plugin_error_counts.get(mod_name, 0) + 1

    def to_dict(self) -> dict[str, Any]:
        """Convert statistics to dictionary summary."""
        return {
            "total_processed_scenes": self.total_processed_scenes,
            "total_events_emitted": self.total_events_emitted,
            "total_execution_time_ms": round(self.total_execution_time_ms, 2),
            "average_execution_time_ms": round(self.average_execution_time_ms, 2),
            "plugin_execution_counts": dict(self.plugin_execution_counts),
            "plugin_error_counts": dict(self.plugin_error_counts),
        }


@dataclass(slots=True)
class RuntimeContext:
    """Execution Context and Dependency Container for the Analytics Runtime Kernel.

    Attributes:
        camera: CameraEntity snapshot representing current camera metadata.
        config: Global runtime configuration dictionary.
        environment: Deployment environment identifier ('development', 'staging', 'production').
        extra_services: Dictionary reserved for injected runtime services (Logger, Metrics, StateStore).
        statistics: RuntimeStatistics tracking kernel execution metrics.
    """

    camera: CameraEntity = field(
        default_factory=lambda: CameraEntity(camera_id="default_cam", camera_name="Default Camera")
    )
    config: dict[str, Any] = field(default_factory=dict)
    environment: str = "production"
    extra_services: dict[str, Any] = field(default_factory=dict)
    statistics: RuntimeStatistics = field(default_factory=RuntimeStatistics)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def get_service(self, service_name: str) -> Optional[Any]:
        """Retrieve an injected runtime service reference by name.

        Args:
            service_name: String service identifier (e.g. 'logger', 'state_store').

        Returns:
            Service reference if registered, None otherwise.
        """
        with self._lock:
            return self.extra_services.get(service_name)

    def register_service(self, service_name: str, service_instance: Any) -> None:
        """Register an injected runtime service instance.

        Args:
            service_name: String service identifier.
            service_instance: Object instance implementing service contract.
        """
        with self._lock:
            self.extra_services[service_name] = service_instance

    def to_dict(self) -> dict[str, Any]:
        """Convert RuntimeContext summary to dictionary."""
        return {
            "camera_id": self.camera.camera_id,
            "camera_name": self.camera.name if hasattr(self.camera, "name") else self.camera.camera_name,
            "environment": self.environment,
            "registered_services": list(self.extra_services.keys()),
            "statistics": self.statistics.to_dict(),
        }
