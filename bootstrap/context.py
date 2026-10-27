"""
Engine Context Component.

Provides top-level runtime engine context encapsulating engine identity,
ServiceRegistry, and active ConfigurationSnapshot.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from camera_analytics.bootstrap.models import ConfigurationSnapshot
from camera_analytics.bootstrap.service_registry import ServiceRegistry


@dataclass(slots=True)
class EngineContext:
    """Top-level Engine Context encapsulating active configuration and services.

    Attributes:
        engine_id: Unique string identifier of this AI Engine.
        node_id: Cluster node identifier.
        environment: Deployment environment ('development', 'staging', 'production').
        snapshot: Immutable ConfigurationSnapshot holding active system configuration.
        services: ServiceRegistry instance containing injected runtime services.
    """

    engine_id: str
    snapshot: ConfigurationSnapshot
    node_id: str = ""
    environment: str = "production"
    services: ServiceRegistry = field(default_factory=ServiceRegistry)

    @property
    def platform(self) -> Any:
        """Return registered RuntimePlatform service."""
        return self.services.get("platform")

    @property
    def video_backend_factory(self) -> Any:
        """Return registered VideoBackendFactory service."""
        return self.services.get("video_backend_factory")

    @property
    def inference_backend_factory(self) -> Any:
        """Return registered InferenceBackendFactory service."""
        return self.services.get("inference_backend_factory")

    @property
    def capabilities(self) -> Any:
        """Return registered RuntimeCapabilityRegistry service."""
        return self.services.get("capability_registry")

    def to_dict(self) -> dict[str, object]:
        """Convert EngineContext summary to dictionary."""
        return {
            "engine_id": self.engine_id,
            "node_id": self.node_id,
            "environment": self.environment,
            "platform": self.platform.name if self.platform else "unknown",
            "pipeline_count": len(self.snapshot.pipelines),
            "registered_services": self.services.list_services(),
            "schema_version": self.snapshot.schema_version,
        }
