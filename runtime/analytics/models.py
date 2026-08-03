"""
Strongly Typed Domain Models for Runtime Analytics Snapshots.
Sprint 4A Enterprise Contract: summary, byZone, byCamera + Legacy Compatibility.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True, slots=True)
class ZoneAnalytics:
    """Zone-level analytics breakdown payload."""
    zone_id: str
    zone_name: str
    metrics: Dict[str, Any]
    reporting_cameras: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zoneId": self.zone_id,
            "zoneName": self.zone_name,
            "metrics": self.metrics,
            "reportingCameras": self.reporting_cameras,
        }


@dataclass(frozen=True, slots=True)
class CameraAnalytics:
    """Camera-level analytics breakdown payload."""
    camera_id: str
    camera_name: str
    metrics: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cameraId": self.camera_id,
            "cameraName": self.camera_name,
            "metrics": self.metrics,
        }


@dataclass(frozen=True, slots=True)
class GenericPluginState:
    """Generic enterprise analytics plugin payload contract (Sprint 4A)."""
    plugin_code: str
    summary: Dict[str, Any]
    by_zone: Dict[str, ZoneAnalytics] = field(default_factory=dict)
    by_camera: Dict[str, CameraAnalytics] = field(default_factory=dict)
    legacy_metrics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "summary": self.summary,
            "byZone": {z_id: z_data.to_dict() for z_id, z_data in self.by_zone.items()},
            "byCamera": {c_id: c_data.to_dict() for c_id, c_data in self.by_camera.items()},
        }
        # Backward Compatibility: Merge legacy top-level metrics directly into root dict
        for k, v in self.legacy_metrics.items():
            if k not in result:
                result[k] = v
        for k, v in self.summary.items():
            if k not in result:
                result[k] = v
        return result


@dataclass(frozen=True, slots=True)
class PeopleCountingState:
    current: int
    entered: int
    exited: int


@dataclass(frozen=True, slots=True)
class QueueDetectionState:
    queue_length: int
    waiting_people: int


@dataclass(frozen=True, slots=True)
class LoiteringState:
    active_count: int
    track_ids: Tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class ZoneOccupancyState:
    occupancy_by_zone: Dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PipelineHealthState:
    fps: float
    latency_ms: float
    inference_time_ms: float
    tracker_time_ms: float
    frame_count: int
    status: str
    engine_version: str = "1.5.0"


@dataclass(frozen=True, slots=True)
class CameraAnalyticsSnapshot:
    camera_id: str
    pipeline_id: str
    timestamp_iso: str
    health: PipelineHealthState
    engine_id: str = "engine_edge_01"
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    schema_version: str = "2.0.0"
    plugin_states: Dict[str, GenericPluginState] = field(default_factory=dict)
    
    # Legacy typed properties for backward compatibility
    people_counting: Optional[PeopleCountingState] = None
    queue_detection: Optional[QueueDetectionState] = None
    loitering: Optional[LoiteringState] = None
    zone_occupancy: Optional[ZoneOccupancyState] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert typed snapshot to camelCase JSON dictionary for transport."""
        plugins_dict: Dict[str, Any] = {}

        # 1. Populate dynamic generic plugin states (Sprint 4A Contract)
        for code, p_state in self.plugin_states.items():
            plugins_dict[code] = p_state.to_dict()

        # 2. Backward compatibility fallback for legacy readers if plugin_states empty
        if "peopleCounting" not in plugins_dict and self.people_counting is not None:
            plugins_dict["peopleCounting"] = {
                "summary": {"current": self.people_counting.current, "entered": self.people_counting.entered, "exited": self.people_counting.exited},
                "byZone": {},
                "byCamera": {self.camera_id: {"cameraId": self.camera_id, "cameraName": self.camera_id, "metrics": {"current": self.people_counting.current}}},
                "current": self.people_counting.current,
                "entered": self.people_counting.entered,
                "exited": self.people_counting.exited,
            }

        if "queueDetection" not in plugins_dict and self.queue_detection is not None:
            plugins_dict["queueDetection"] = {
                "summary": {"queueLength": self.queue_detection.queue_length, "waitingPeople": self.queue_detection.waiting_people},
                "byZone": {},
                "byCamera": {self.camera_id: {"cameraId": self.camera_id, "cameraName": self.camera_id, "metrics": {"queueLength": self.queue_detection.queue_length}}},
                "queueLength": self.queue_detection.queue_length,
                "waitingPeople": self.queue_detection.waiting_people,
            }

        if "loitering" not in plugins_dict and self.loitering is not None:
            plugins_dict["loitering"] = {
                "summary": {"active": self.loitering.active_count},
                "byZone": {},
                "byCamera": {self.camera_id: {"cameraId": self.camera_id, "cameraName": self.camera_id, "metrics": {"active": self.loitering.active_count}}},
                "active": self.loitering.active_count,
                "trackIds": list(self.loitering.track_ids),
            }

        if "zoneOccupancy" not in plugins_dict and self.zone_occupancy is not None:
            plugins_dict["zoneOccupancy"] = {
                "summary": {"totalOccupancy": sum(self.zone_occupancy.occupancy_by_zone.values()) if self.zone_occupancy.occupancy_by_zone else 0},
                "byZone": {
                    z_id: {
                        "zoneId": z_id,
                        "zoneName": z_id.replace("_", " ").title(),
                        "metrics": {"occupancyCount": count},
                        "reportingCameras": [self.camera_id],
                    }
                    for z_id, count in self.zone_occupancy.occupancy_by_zone.items()
                },
                "byCamera": {},
                "occupancyByZone": self.zone_occupancy.occupancy_by_zone,
            }

        return {
            "messageId": self.message_id,
            "schemaVersion": self.schema_version,
            "engineId": self.engine_id,
            "cameraId": self.camera_id,
            "pipelineId": self.pipeline_id,
            "timestamp": self.timestamp_iso,
            "health": {
                "fps": round(self.health.fps, 1),
                "latencyMs": round(self.health.latency_ms, 2),
                "inferenceTimeMs": round(self.health.inference_time_ms, 2),
                "trackerTimeMs": round(self.health.tracker_time_ms, 2),
                "frameCount": self.health.frame_count,
                "status": self.health.status,
                "engineVersion": self.health.engine_version,
            },
            "plugins": plugins_dict,
        }
