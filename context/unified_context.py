"""
Unified Analytics Context data structure for shared AI inference runtime.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class SharedAnalyticsContext:
    """Unified AI Runtime Context constructed once per video frame.

    Eliminates duplicated inference by sharing detection, tracking, pose keypoints,
    and spatial zone mappings across all active analytics plugins.
    """

    frame: Any = None
    frame_index: int = 0
    timestamp_utc: float = field(default_factory=time.time)

    camera_id: str = "c1"
    camera_name: str = "CAM-01 Main Lobby"
    pipeline_id: str = "pipeline_default"
    engine_instance_id: str = "engine_edge_01"

    # Shared AI Inference Artifacts (Computed EXACTLY ONCE per frame)
    detections: list[dict[str, Any]] = field(default_factory=list)
    tracks: list[dict[str, Any]] = field(default_factory=list)
    pose_keypoints: list[Any] = field(default_factory=list)
    zones: list[Any] = field(default_factory=list)
    zone_results: dict[str, Any] = field(default_factory=dict)
    spatial_snapshot: Any = None
    plugin_repository: Any = None

    # Observability Stage Timings (in milliseconds)
    stage_timings_ms: dict[str, float] = field(
        default_factory=lambda: {
            "detection_time_ms": 0.0,
            "tracking_time_ms": 0.0,
            "reid_time_ms": 0.0,
            "pose_time_ms": 0.0,
            "zone_mapping_time_ms": 0.0,
            "plugin_execution_time_ms": 0.0,
            "event_dispatch_time_ms": 0.0,
        }
    )

    metadata: dict[str, Any] = field(default_factory=dict)
    telemetry: dict[str, Any] = field(default_factory=dict)
    configuration: dict[str, Any] = field(default_factory=dict)

    @property
    def active_person_count(self) -> int:
        """Helper property returning count of currently tracked persons."""
        return len(self.tracks) if self.tracks else len([d for d in self.detections if d.get("class") == "person"])
