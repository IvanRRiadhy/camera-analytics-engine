"""
CollectorContext Parameter Container (Sprint H1.5D1.5 / H1.5D1.6).

Explicit parameter context passed to telemetry collectors (collector.collect(context)).
Eliminates reliance on global singletons or ambient state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class CollectorContext:
    """Explicit context container passed to TelemetryCollector instances."""

    engine_id: str = "engine_standalone_01"
    device: str = "cuda:0"
    engine_mode: str = "standalone"
    pipelines: Any = None
    model_manager: Any = None
    scheduler: Any = None
    human_runtime: Any = None
    zone_engine: Any = None
    active_camera_ids: list[str] = field(default_factory=list)
    custom_context: dict[str, Any] = field(default_factory=dict)
