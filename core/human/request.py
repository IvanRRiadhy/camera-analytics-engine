"""
Human Inference Request & Zero-Copy ROICropHandle Abstraction (Sprint H1.4.7).

Provides immutable, standardized inference request objects passed from HumanRepresentation
to HumanAnalyticsScheduler, keeping crop memory allocations zero-copy via ROICropHandle.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence
import numpy as np
from numpy.typing import NDArray

from camera_analytics.core.human.models import HumanRepresentation, ROICropCache
from camera_analytics.core.spatial.models import PixelPoint
from camera_analytics.models.detection import BoundingBox, PoseKeypoints


@dataclass(frozen=True, slots=True)
class ROICropHandle:
    """Lightweight zero-copy reference to pre-extracted sub-image crops in ROICropCache.

    Prevents duplicating heavy raw NumPy image arrays across modules.
    """

    crop_cache_ref: ROICropCache

    @property
    def face_crop(self) -> Optional[NDArray[np.uint8]]:
        """Access face crop from underlying cache."""
        return self.crop_cache_ref.face_crop

    @property
    def head_crop(self) -> Optional[NDArray[np.uint8]]:
        """Access head crop from underlying cache."""
        return self.crop_cache_ref.head_crop

    @property
    def torso_crop(self) -> Optional[NDArray[np.uint8]]:
        """Access torso crop from underlying cache."""
        return self.crop_cache_ref.torso_crop

    @property
    def body_crop(self) -> Optional[NDArray[np.uint8]]:
        """Access body crop (head or torso) from underlying cache."""
        return self.crop_cache_ref.head_crop if self.crop_cache_ref.head_crop is not None else self.crop_cache_ref.torso_crop


@dataclass(frozen=True, slots=True)
class HumanInferenceRequest:
    """Immutable, model-agnostic AI inference request container.

    Decouples AI modules from direct dependency on HumanRepresentation and frame arrays.
    """

    track_id: int
    timestamp_utc: float
    frame_index: int
    crop_handle: ROICropHandle
    body_bbox: BoundingBox
    face_roi: Optional[BoundingBox] = None
    head_roi: Optional[BoundingBox] = None
    ground_point: Optional[PixelPoint] = None
    pose_keypoints: Optional[PoseKeypoints] = None
    visibility_score: float = 1.0
    face_quality_score: float = 0.0
    occlusion_state: str = "NONE"
    camera_id: str = "default_camera"
    pipeline_id: str = "default_pipeline"
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_representation(
        cls,
        representation: HumanRepresentation,
        camera_id: str = "default_camera",
        pipeline_id: str = "default_pipeline",
        metadata: Optional[dict[str, Any]] = None,
    ) -> HumanInferenceRequest:
        """Factory constructor creating a HumanInferenceRequest from HumanRepresentation."""
        handle = ROICropHandle(crop_cache_ref=representation.crop_cache)
        return cls(
            track_id=representation.track_id,
            timestamp_utc=representation.timestamp_utc,
            frame_index=representation.frame_index,
            crop_handle=handle,
            body_bbox=representation.body_bbox,
            face_roi=representation.face_roi,
            head_roi=representation.head_roi,
            ground_point=representation.ground_point,
            pose_keypoints=representation.pose_keypoints,
            visibility_score=representation.visibility_score,
            face_quality_score=representation.face_quality_score,
            occlusion_state=representation.occlusion_state,
            camera_id=camera_id,
            pipeline_id=pipeline_id,
            metadata=metadata or {},
        )
