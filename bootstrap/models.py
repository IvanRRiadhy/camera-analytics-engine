"""
Bootstrap configuration domain models for the camera analytics platform.

Defines strongly-typed, immutable dataclass schemas for engine configuration,
pipeline configuration wrappers, runtime settings, and root configuration snapshots.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from camera_analytics.config.schema import AppConfig


@dataclass(frozen=True, slots=True)
class EngineConfig:
    """Configuration for engine identity and deployment mode.

    Attributes:
        engine_id: Unique identifier for this engine instance.
        node_id: Cluster node identifier.
        hostname: Machine hostname.
        mode: Operational mode ('standalone' or 'enterprise').
        log_level: System logging verbosity level.
        schema_version: Schema version string for configuration versioning.
    """

    engine_id: str
    node_id: str = ""
    hostname: str = ""
    mode: str = "standalone"
    log_level: str = "INFO"
    schema_version: str = "1.0.0"


@dataclass(frozen=True, slots=True)
class PipelineConfiguration:
    """Wrapper coupling a camera pipeline identity with its AppConfig.

    Attributes:
        pipeline_id: Unique pipeline identifier (e.g. 'pipe_cam_lobby_01').
        camera_id: Camera identifier associated with this pipeline.
        gpu_id: GPU index assigned to run this pipeline (default 0).
        enabled: Whether this camera pipeline is active.
        app: Validated AppConfig instance for this pipeline.
    """

    pipeline_id: str
    camera_id: str
    app: AppConfig
    gpu_id: int = 0
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class PublisherEntryConfig:
    """Configuration for a single event publisher plugin.

    Attributes:
        publisher_type: Registered publisher string identifier (e.g. 'log', 'mqtt', 'rabbitmq').
        name: Instance name identifier.
        enabled: Whether the publisher is enabled.
        settings: Connection and transport settings dictionary.
    """

    publisher_type: str
    name: str = ""
    enabled: bool = True
    settings: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PublishersConfig:
    """Collection of event publisher configurations.

    Attributes:
        publishers: Tuple of PublisherEntryConfig objects.
        schema_version: Schema version string.
    """

    publishers: tuple[PublisherEntryConfig, ...] = ()
    schema_version: str = "1.0.0"


@dataclass(frozen=True, slots=True)
class EngineRuntimeConfig:
    """Configuration for engine runtime kernel defaults and plugin discovery.

    Attributes:
        plugin_directory: Directory path for dynamic plugin discovery.
        diagnostics_enabled: Whether diagnostic metrics collector is active.
        max_module_latency_ms: Latency threshold before flagging module warnings.
        schema_version: Schema version string.
    """

    plugin_directory: str = "camera_analytics/plugins"
    diagnostics_enabled: bool = True
    max_module_latency_ms: float = 100.0
    schema_version: str = "1.0.0"


@dataclass(frozen=True, slots=True)
class ConfigurationSnapshot:
    """Immutable root configuration snapshot holding all engine settings.

    Attributes:
        schema_version: Root configuration schema version string.
        engine: Engine identity and mode configuration.
        pipelines: Tuple of active PipelineConfiguration objects.
        publishers: Publisher collection configuration.
        runtime: Engine runtime kernel configuration.
    """

    engine: EngineConfig
    pipelines: tuple[PipelineConfiguration, ...]
    publishers: PublishersConfig
    runtime: EngineRuntimeConfig
    schema_version: str = "1.0.0"
