"""
Validation Framework Data Schemas & Models.

Defines strongly typed data structures for ground truth annotations, dataset manifests,
matching tolerances, evaluation results, system resource metrics, and baseline comparisons.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class MatchStatus(Enum):
    """Classification status for event comparison."""

    TRUE_POSITIVE = "TP"   # Expected event matched runtime event within tolerance
    FALSE_POSITIVE = "FP"  # Runtime event generated with no expected ground truth
    FALSE_NEGATIVE = "FN"  # Expected ground truth event missed by runtime


@dataclass(frozen=True, slots=True)
class CameraFeedConfig:
    """Configuration for a single camera feed in a dataset.

    Attributes:
        camera_id: Unique string camera identifier.
        video_file: Relative path to recorded video file.
        resolution: Tuple of (width, height) in pixels.
        fps: Recorded video frame rate.
    """

    camera_id: str
    video_file: str
    resolution: tuple[int, int] = (1920, 1080)
    fps: float = 30.0


@dataclass(frozen=True, slots=True)
class DatasetManifest:
    """Metadata manifest describing a validation dataset.

    Attributes:
        dataset_id: Unique string dataset identifier (e.g. 'ds_lobby_01').
        version: Dataset version string (e.g. '1.0.0').
        name: Human-readable dataset name.
        description: Scenario and context description.
        scenario: Operational scenario classification (e.g. 'PEAK_FLOW').
        camera_profile: Camera hardware profile (e.g. '1080p_wide_angle').
        tags: List of descriptive tags for filtering (e.g. ['indoor', 'lobby', 'low_light']).
        cameras: Dictionary mapping camera_id to CameraFeedConfig.
        duration_seconds: Total recorded video duration in seconds.
        frame_count: Total frame count.
    """

    dataset_id: str
    version: str = "1.0.0"
    name: str = ""
    description: str = ""
    scenario: str = "DEFAULT"
    camera_profile: str = "default_profile"
    tags: list[str] = field(default_factory=list)
    cameras: dict[str, CameraFeedConfig] = field(default_factory=dict)
    duration_seconds: float = 0.0
    frame_count: int = 0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DatasetManifest:
        """Parse DatasetManifest from a dictionary."""
        cameras_dict = {}
        if "cameras" in data and isinstance(data["cameras"], dict):
            for cam_id, cam_info in data["cameras"].items():
                res = tuple(cam_info.get("resolution", [1920, 1080]))
                cameras_dict[cam_id] = CameraFeedConfig(
                    camera_id=cam_id,
                    video_file=cam_info.get("video_file", "video.mp4"),
                    resolution=(int(res[0]), int(res[1])),
                    fps=float(cam_info.get("fps", 30.0)),
                )

        return cls(
            dataset_id=data.get("dataset_id", "unknown_ds"),
            version=data.get("version", "1.0.0"),
            name=data.get("name", ""),
            description=data.get("description", ""),
            scenario=data.get("scenario", "DEFAULT"),
            camera_profile=data.get("camera_profile", "default_profile"),
            tags=list(data.get("tags", [])),
            cameras=cameras_dict,
            duration_seconds=float(data.get("duration_seconds", 0.0)),
            frame_count=int(data.get("frame_count", 0)),
        )


@dataclass(slots=True)
class GroundTruthEvent:
    """Annotated ground truth expected event schema.

    Attributes:
        frame_index: Expected frame index when event occurs.
        timestamp: Expected timestamp in seconds.
        event_type: String classification (e.g. 'ZONE_ENTER', 'LOITERING').
        camera_id: Associated camera identifier.
        track_id: Optional associated track ID.
        zone_id: Optional associated zone ID.
        severity: Event severity ('INFO', 'WARNING', 'ALERT', 'CRITICAL').
        expected_duration: Optional expected duration in seconds (for loitering/dwell).
        notes: Annotator notes.
    """

    frame_index: int
    timestamp: float
    event_type: str
    camera_id: str = "default_cam"
    track_id: Optional[int] = None
    zone_id: Optional[str] = None
    severity: str = "INFO"
    expected_duration: Optional[float] = None
    notes: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GroundTruthEvent:
        """Parse GroundTruthEvent from dictionary."""
        return cls(
            frame_index=int(data["frame_index"]),
            timestamp=float(data.get("timestamp", 0.0)),
            event_type=data["event_type"],
            camera_id=data.get("camera_id", "default_cam"),
            track_id=data.get("track_id"),
            zone_id=data.get("zone_id"),
            severity=data.get("severity", "INFO"),
            expected_duration=data.get("expected_duration"),
            notes=data.get("notes", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert GroundTruthEvent to dictionary."""
        return {
            "frame_index": self.frame_index,
            "timestamp": round(self.timestamp, 3),
            "event_type": self.event_type,
            "camera_id": self.camera_id,
            "track_id": self.track_id,
            "zone_id": self.zone_id,
            "severity": self.severity,
            "expected_duration": self.expected_duration,
            "notes": self.notes,
        }


@dataclass(frozen=True, slots=True)
class ValidationTolerance:
    """Configuration parameters for event matching tolerances.

    Attributes:
        frame_tolerance: Maximum frame difference allowed for matching.
        time_tolerance: Maximum timestamp difference in seconds allowed for matching.
        match_track_id: Whether track ID must match when present.
        match_zone_id: Whether zone ID must match when present.
    """

    frame_tolerance: int = 15
    time_tolerance: float = 1.0
    match_track_id: bool = True
    match_zone_id: bool = True


@dataclass(slots=True)
class EventMatchResult:
    """Result of matching a ground truth event against runtime outputs.

    Attributes:
        status: Match classification (TP, FP, FN).
        ground_truth: Optional ground truth event instance.
        generated_event: Optional runtime event dictionary.
        detection_delay_frames: Frame delay between ground truth and generation.
        detection_delay_seconds: Time delay in seconds between ground truth and generation.
    """

    status: MatchStatus
    ground_truth: Optional[GroundTruthEvent] = None
    generated_event: Optional[dict[str, Any]] = None
    detection_delay_frames: int = 0
    detection_delay_seconds: float = 0.0


@dataclass(slots=True)
class SystemResourceMetrics:
    """System resource and throughput evaluation metrics.

    Attributes:
        cpu_utilization_pct: Average CPU usage percentage during run.
        memory_mb: Peak/average memory consumption in megabytes.
        gpu_utilization_pct: Average GPU utilization percentage.
        gpu_memory_mb: Peak GPU memory allocation in megabytes.
        avg_latency_ms: Average per-frame pipeline execution latency in ms.
        throughput_fps: Overall frame processing throughput speed in FPS.
    """

    cpu_utilization_pct: float = 0.0
    memory_mb: float = 0.0
    gpu_utilization_pct: float = 0.0
    gpu_memory_mb: float = 0.0
    avg_latency_ms: float = 0.0
    throughput_fps: float = 0.0

    def to_dict(self) -> dict[str, float]:
        """Convert SystemResourceMetrics to dictionary."""
        return {
            "cpu_utilization_pct": round(self.cpu_utilization_pct, 1),
            "memory_mb": round(self.memory_mb, 1),
            "gpu_utilization_pct": round(self.gpu_utilization_pct, 1),
            "gpu_memory_mb": round(self.gpu_memory_mb, 1),
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "throughput_fps": round(self.throughput_fps, 1),
        }


@dataclass(slots=True)
class AnalyticsModuleMetrics:
    """Accuracy metrics for a specific analytics module or event type.

    Attributes:
        true_positives: Count of correctly matched events (TP).
        false_positives: Count of unexpected generated events (FP).
        false_negatives: Count of missed ground truth events (FN).
        precision: Precision score (0.0 to 1.0).
        recall: Recall score (0.0 to 1.0).
        f1_score: F1 metric (0.0 to 1.0).
        accuracy: Accuracy score (0.0 to 1.0).
        avg_detection_delay_ms: Mean event detection delay in milliseconds.
    """

    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    accuracy: float = 0.0
    avg_detection_delay_ms: float = 0.0

    def calculate(self) -> None:
        """Compute precision, recall, f1, and accuracy from TP, FP, FN."""
        tp, fp, fn = self.true_positives, self.false_positives, self.false_negatives
        self.precision = tp / max(1, tp + fp) if (tp + fp) > 0 else 0.0
        self.recall = tp / max(1, tp + fn) if (tp + fn) > 0 else 0.0
        if (self.precision + self.recall) > 0:
            self.f1_score = 2 * (self.precision * self.recall) / (self.precision + self.recall)
        else:
            self.f1_score = 0.0
        self.accuracy = tp / max(1, tp + fp + fn) if (tp + fp + fn) > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to clean dictionary."""
        return {
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1_score": round(self.f1_score, 4),
            "accuracy": round(self.accuracy, 4),
            "avg_detection_delay_ms": round(self.avg_detection_delay_ms, 2),
        }
