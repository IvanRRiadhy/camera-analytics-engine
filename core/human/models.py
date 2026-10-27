"""
Core Human Domain Models (Sprint H1.5C).

Defines persistent domain representations:
- CapabilityId: Enum of supported human capability types.
- HumanStateLifecycle: State machine enumeration (NEW -> INITIALIZING -> LEARNING -> STABLE -> LOST -> TERMINATED).
- HumanStatistics: Track lifetime, inference counts, latency, and quality telemetry.
- CapabilityState: Modular state container for a single capability.
- HumanState: Persistent person intelligence state surviving across inference cycles.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Sequence
import numpy as np
from numpy.typing import NDArray

from camera_analytics.core.spatial.models import GroundPointSource, PixelPoint
from camera_analytics.models.detection import BoundingBox, Keypoint, PoseKeypoints


class CapabilityId(str, Enum):
    """Enum of human analytics capability types."""

    AGE = "AGE"
    GENDER = "GENDER"
    EMOTION = "EMOTION"
    FACE_RECOGNITION = "FACE_RECOGNITION"
    PPE = "PPE"
    GESTURE = "GESTURE"
    OCR = "OCR"
    CLOTHING = "CLOTHING"
    FATIGUE = "FATIGUE"


class HumanStateLifecycle(str, Enum):
    """Lifecycle state machine for a persistent tracked person."""

    NEW = "NEW"
    INITIALIZING = "INITIALIZING"
    LEARNING = "LEARNING"
    STABLE = "STABLE"
    LOST = "LOST"
    TERMINATED = "TERMINATED"


@dataclass
class CapabilityHistory:
    """Historical sliding window of recent predictions for a capability."""

    window: deque = field(default_factory=lambda: deque(maxlen=15))

    def append(self, val: Any, conf: float) -> None:
        self.window.append((val, conf))

    def clear(self) -> None:
        self.window.clear()


@dataclass
class CapabilityStabilization:
    """Stabilization parameters and state for a capability."""

    ema_value: Optional[float] = None
    lock_state: str = "UNLOCKED"          # "UNLOCKED" | "LOCKING" | "LOCKED" | "EXPIRED"
    decay_factor: float = 1.0


@dataclass
class CapabilityState:
    """Modular state container for a single AI capability (e.g. Age, Gender, Emotion, PPE)."""

    capability_id: CapabilityId
    current_value: Any = None
    confidence: float = 0.0
    quality_score: float = 0.0
    first_seen_utc: float = field(default_factory=time.time)
    last_seen_utc: float = field(default_factory=time.time)
    inference_count: int = 0
    history: CapabilityHistory = field(default_factory=CapabilityHistory)
    stabilization: CapabilityStabilization = field(default_factory=CapabilityStabilization)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class HumanStatistics:
    """Aggregated operational statistics and quality telemetry for a tracked person."""

    track_lifetime_s: float = 0.0
    inference_count: int = 0
    skipped_count: int = 0
    success_count: int = 0
    average_quality_score: float = 0.0
    last_inference_latency_ms: float = 0.0
    total_quality_sum: float = 0.0

    def record_inference(self, latency_ms: float, quality_score: float, success: bool = True) -> None:
        self.inference_count += 1
        if success:
            self.success_count += 1
        self.last_inference_latency_ms = latency_ms
        self.total_quality_sum += quality_score
        self.average_quality_score = round(self.total_quality_sum / self.inference_count, 3)

    def record_skip(self) -> None:
        self.skipped_count += 1


@dataclass
class ROICropCache:
    """Zero-copy memory cache for cropped sub-images during single-frame pipeline execution."""

    head_crop: Optional[NDArray[np.uint8]] = None
    face_crop: Optional[NDArray[np.uint8]] = None
    aligned_face_crop: Optional[NDArray[np.uint8]] = None
    torso_crop: Optional[NDArray[np.uint8]] = None
    upper_body_crop: Optional[NDArray[np.uint8]] = None
    lower_body_crop: Optional[NDArray[np.uint8]] = None
    body_crop: Optional[NDArray[np.uint8]] = None


@dataclass(frozen=True, slots=True)
class HumanRepresentation:
    """Non-inference geometric & spatial representation of a person track."""

    track_id: int
    frame_index: int
    timestamp_utc: float

    # 1. Bounding Boxes & ROIs
    body_bbox: BoundingBox
    head_roi: Optional[BoundingBox] = None
    face_roi: Optional[BoundingBox] = None
    torso_roi: Optional[BoundingBox] = None
    upper_body_roi: Optional[BoundingBox] = None
    lower_body_roi: Optional[BoundingBox] = None

    # 2. Keypoints & Spatial Anchors
    pose_keypoints: Optional[PoseKeypoints] = None
    ground_point: PixelPoint = field(default_factory=lambda: PixelPoint(0, 0))
    ground_point_source: GroundPointSource = GroundPointSource.BBOX_BOTTOM_CENTER

    # 3. Visibility & Quality Metrics
    visibility_score: float = 1.0
    occlusion_state: str = "NONE"
    face_quality_score: float = 0.0
    body_quality_score: float = 0.0

    # 4. Embedded ROI Crop Cache
    crop_cache: ROICropCache = field(default_factory=ROICropCache)


@dataclass(slots=True)
class DemographicsState:
    """Demographic attributes (Age, Gender) with Attribute Locks."""

    gender: Optional[str] = None
    gender_confidence: float = 0.0
    gender_lock: str = "UNLOCKED"
    age: Optional[float] = None
    age_group: str = "UNKNOWN"
    age_confidence: float = 0.0
    age_lock: str = "UNLOCKED"


@dataclass(slots=True)
class ExpressionState:
    """Facial expression and emotional engagement attributes."""

    primary_emotion: str = "NEUTRAL"
    confidence: float = 0.0
    engagement_score: float = 0.0
    expression_lock: str = "UNLOCKED"


@dataclass(slots=True)
class IdentityState:
    """Person recognition and face feature embedding attributes."""

    person_id: Optional[str] = None
    category: str = "UNKNOWN"
    recognition_confidence: float = 0.0
    face_embedding: Optional[NDArray[np.float32]] = None
    identity_lock: str = "UNLOCKED"


@dataclass(slots=True)
class PPEState:
    """Personal Protective Equipment compliance attributes."""

    helmet: str = "UNKNOWN"
    mask: str = "UNKNOWN"
    vest: str = "UNKNOWN"
    ppe_lock: str = "UNLOCKED"


@dataclass(slots=True)
class AppearanceState:
    """Upper/lower body clothing attributes and color embeddings."""

    upper_color: str = "UNKNOWN"
    lower_color: str = "UNKNOWN"
    clothing_type: str = "UNKNOWN"
    appearance_lock: str = "UNLOCKED"


@dataclass(slots=True)
class BehaviorCueState:
    """Gesture and physical action cues."""

    phone_usage: bool = False
    smoking: bool = False
    gesture: str = "NONE"
    behavior_lock: str = "UNLOCKED"


BehaviorCuesState = BehaviorCueState


class HumanState:
    """Persistent person intelligence domain model surviving across inference cycles."""

    def __init__(self, track_id: int) -> None:
        from camera_analytics.core.human.timeline import HumanTimeline
        self.track_id: int = track_id
        self.lifecycle: HumanStateLifecycle = HumanStateLifecycle.NEW
        self.first_seen_utc: float = time.time()
        self.last_seen_utc: float = time.time()
        self.statistics: HumanStatistics = HumanStatistics()
        self.capabilities: dict[CapabilityId, CapabilityState] = {}
        self.timeline: HumanTimeline = HumanTimeline(max_entries=100)

        # Legacy backward-compatibility structures
        self.demographics: DemographicsState = DemographicsState()
        self.expression: ExpressionState = ExpressionState()
        self.identity: IdentityState = IdentityState()
        self.ppe: PPEState = PPEState()
        self.appearance: AppearanceState = AppearanceState()
        self.behavior: BehaviorCueState = BehaviorCueState()
        self.custom_attributes: dict[str, Any] = {}

    @property
    def is_locked(self) -> bool:
        """Return True if all core attributes (demographics) are locked."""
        return (
            self.demographics.gender_lock == "LOCKED"
            and self.demographics.age_lock == "LOCKED"
        )

    @property
    def is_active(self) -> bool:
        """Return True if track is active and not terminated."""
        return self.lifecycle not in (HumanStateLifecycle.LOST, HumanStateLifecycle.TERMINATED)

    @property
    def track_lifetime_s(self) -> float:
        """Return track lifetime in seconds."""
        return round(self.last_seen_utc - self.first_seen_utc, 2)

    def get_capability_state(self, cap_id: CapabilityId) -> CapabilityState:
        """Retrieve or instantiate CapabilityState for a capability."""
        if cap_id not in self.capabilities:
            self.capabilities[cap_id] = CapabilityState(capability_id=cap_id)
        return self.capabilities[cap_id]
