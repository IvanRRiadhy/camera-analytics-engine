"""
Service Manifest Specification & Parser.

Parses and validates `manifest.json` definitions for Event Service Plugins.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass(slots=True)
class RetryPolicyConfig:
    """Retry policy settings."""

    max_retries: int = 3
    backoff_sec: float = 1.0


@dataclass(slots=True)
class QueueSettingsConfig:
    """Queue Settings."""

    max_queue_size: int = 1000


@dataclass(slots=True)
class ServiceManifest:
    """Service Plugin Metadata Specification.

    Attributes:
        service_name: Unique service string identifier.
        version: Semantic version string.
        description: Human-readable service summary.
        event_types: List of event type subscriptions (or ['*']).
        capabilities: List of capability string keys provided by this service.
        dependencies: List of capability string keys required before starting.
        execution_mode: 'IMMEDIATE', 'ASYNC', 'BATCH', or 'SCHEDULED'.
        priority: Execution priority integer (lower = higher priority).
        enabled: Default enabled state.
        entry_point: Python module entry point (e.g. 'plugin:RecordingServicePlugin').
        config_schema: JSON schema dictionary for CMS configuration validation.
        retry_policy: Retry policy configuration.
        queue_settings: Queue configuration.
    """

    service_name: str
    version: str
    description: str = ""
    event_types: list[str] = field(default_factory=lambda: ["*"])
    capabilities: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    execution_mode: str = "IMMEDIATE"  # IMMEDIATE, ASYNC, BATCH, SCHEDULED
    priority: int = 10
    enabled: bool = True
    entry_point: str = "plugin:ServicePlugin"
    config_schema: dict[str, Any] = field(default_factory=dict)
    retry_policy: RetryPolicyConfig = field(default_factory=RetryPolicyConfig)
    queue_settings: QueueSettingsConfig = field(default_factory=QueueSettingsConfig)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ServiceManifest:
        """Construct ServiceManifest from dictionary."""
        retry_data = data.get("retry_policy", {})
        retry_cfg = RetryPolicyConfig(
            max_retries=retry_data.get("max_retries", 3),
            backoff_sec=retry_data.get("backoff_sec", 1.0),
        )

        queue_data = data.get("queue_settings", {})
        queue_cfg = QueueSettingsConfig(
            max_queue_size=queue_data.get("max_queue_size", 1000)
        )

        return cls(
            service_name=data["service_name"],
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            event_types=data.get("event_types", ["*"]),
            capabilities=data.get("capabilities", []),
            dependencies=data.get("dependencies", []),
            execution_mode=data.get("execution_mode", "IMMEDIATE").upper(),
            priority=data.get("priority", 10),
            enabled=data.get("enabled", True),
            entry_point=data.get("entry_point", "plugin:ServicePlugin"),
            config_schema=data.get("config_schema", {}),
            retry_policy=retry_cfg,
            queue_settings=queue_cfg,
        )

    @classmethod
    def from_file(cls, manifest_path: str | Path) -> ServiceManifest:
        """Parse ServiceManifest from JSON file."""
        path = Path(manifest_path)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)
