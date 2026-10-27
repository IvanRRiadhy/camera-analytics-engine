"""
Face Quality Estimator.

Calculates composite face quality score (0.0 to 1.0) evaluating:
1. Laplacian Variance (Image Sharpness).
2. Face Bounding Box Resolution.
3. Keypoint Visibility Ratio (Keypoints #0-#4: Nose, Eyes, Ears).
4. Facial Symmetry & Orientation Alignment.
"""

from __future__ import annotations

import logging
from typing import Any, Optional, Sequence
import cv2
import numpy as np
from numpy.typing import NDArray

from camera_analytics.models.detection import BoundingBox, Keypoint, PoseKeypoints

logger = logging.getLogger(__name__)


class FaceQualityEstimator:
    """Estimates face quality score for downstream AI module gating."""

    @staticmethod
    def evaluate_quality(
        face_crop: Optional[NDArray[np.uint8]],
        face_bbox: Optional[BoundingBox] = None,
        pose_keypoints: Optional[PoseKeypoints] = None,
    ) -> float:
        """Calculate normalized face quality score in [0.0, 1.0]."""
        if face_crop is None or face_crop.size == 0:
            return 0.0

        h, w = face_crop.shape[:2]
        if h < 10 or w < 10:
            return 0.0

        # 1. Resolution Score (Target: >= 64x64 px)
        min_dim = min(h, w)
        resolution_score = min(1.0, min_dim / 64.0)

        # 2. Sharpness Score via Laplacian Variance
        gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY) if len(face_crop.shape) == 3 else face_crop
        variance = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        # Map variance (0 - 500) to 0.0 - 1.0
        sharpness_score = min(1.0, variance / 250.0)

        # 3. Keypoint Visibility & Alignment Score
        keypoint_score = 0.5
        if pose_keypoints and hasattr(pose_keypoints, "keypoints"):
            kps = pose_keypoints.keypoints
            if len(kps) >= 5:
                # Keypoints #0: Nose, #1: Left Eye, #2: Right Eye, #3: Left Ear, #4: Right Ear
                nose, le, re, lear, rear = kps[0], kps[1], kps[2], kps[3], kps[4]
                head_confs = [getattr(kp, "confidence", 0.0) for kp in (nose, le, re, lear, rear)]
                avg_conf = sum(head_confs) / len(head_confs)

                # Symmetry check between eyes and nose
                eye_dist = abs(re.x - le.x) if (re.confidence > 0.3 and le.confidence > 0.3) else 0.0
                if eye_dist > 5.0 and nose.confidence > 0.3:
                    # Frontal alignment: Nose should be roughly between eyes
                    nose_eye_ratio = abs(nose.x - (le.x + re.x) / 2.0) / eye_dist
                    alignment_bonus = max(0.0, 1.0 - nose_eye_ratio)
                    keypoint_score = 0.4 * avg_conf + 0.6 * alignment_bonus
                else:
                    keypoint_score = avg_conf

        # Composite Weighted Score
        quality_score = (
            0.4 * sharpness_score +
            0.35 * resolution_score +
            0.25 * keypoint_score
        )

        return round(float(np.clip(quality_score, 0.0, 1.0)), 3)
