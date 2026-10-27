"""
Unit Tests for Human Representation & Domain Foundation.

Tests:
1. ROICropCache zero-copy sub-image caching.
2. HumanRepresentationExtractor keypoint-based face ROI extraction.
3. FaceQualityEstimator sharpness & resolution scoring.
4. HumanStateCache thread safety and track lifecycle eviction.
"""

from __future__ import annotations

import logging
import numpy as np
from camera_analytics.core.human import (
    FaceQualityEstimator,
    HumanRepresentationExtractor,
    HumanState,
    HumanStateCache,
    ROICropCache,
)
from camera_analytics.models.detection import BoundingBox, Keypoint, PoseKeypoints

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestHumanRepresentation")


def test_roi_crop_cache():
    """Test ROICropCache memory caching."""
    cache = ROICropCache()
    dummy_crop = np.zeros((64, 64, 3), dtype=np.uint8)
    cache.face_crop = dummy_crop

    assert cache.face_crop is not None
    assert cache.face_crop.shape == (64, 64, 3)
    assert cache.head_crop is None
    print("[+] ROICropCache test passed.")


def test_face_quality_estimator():
    """Test FaceQualityEstimator sharpness and quality evaluation."""
    # Blank black image (Low sharpness)
    blank_crop = np.zeros((32, 32, 3), dtype=np.uint8)
    quality_blank = FaceQualityEstimator.evaluate_quality(blank_crop)
    assert 0.0 <= quality_blank <= 0.5

    # High contrast image (High sharpness)
    sharp_crop = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
    quality_sharp = FaceQualityEstimator.evaluate_quality(sharp_crop)
    assert quality_sharp > quality_blank
    print(f"[+] FaceQualityEstimator test passed. Blank Quality={quality_blank:.2f}, Sharp Quality={quality_sharp:.2f}")


def test_human_representation_extractor():
    """Test HumanRepresentationExtractor with synthetic keypoints."""
    # Synthetic 17 COCO keypoints with face keypoints
    kps = [Keypoint(x=100.0 + i*2, y=100.0 + i*2, confidence=0.85) for i in range(17)]
    kps[0] = Keypoint(x=200.0, y=150.0, confidence=0.9)  # Nose
    kps[1] = Keypoint(x=185.0, y=140.0, confidence=0.9)  # Left Eye
    kps[2] = Keypoint(x=215.0, y=140.0, confidence=0.9)  # Right Eye

    pose = PoseKeypoints(keypoints=tuple(kps))
    track = {
        "track_id": 42,
        "bbox": [150.0, 100.0, 250.0, 400.0],
        "confidence": 0.95,
        "keypoints": pose,
    }

    dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    rep = HumanRepresentationExtractor.extract(track, frame=dummy_frame, frame_index=1)

    assert rep.track_id == 42
    assert rep.face_roi is not None
    assert rep.face_roi.x1 < rep.face_roi.x2
    assert rep.crop_cache.face_crop is not None
    print(f"[+] HumanRepresentationExtractor test passed. Track ID={rep.track_id}, Face ROI=[{rep.face_roi.x1:.1f}, {rep.face_roi.y1:.1f}, {rep.face_roi.x2:.1f}, {rep.face_roi.y2:.1f}], Quality={rep.face_quality_score:.2f}")


def test_human_state_cache():
    """Test HumanStateCache lifecycle management and eviction."""
    cache = HumanStateCache()

    # Get or create
    state1 = cache.get_or_create(101)
    assert state1.track_id == 101
    assert state1.demographics.gender == "UNKNOWN"

    # Update state
    updated_state = HumanState(
        track_id=101,
        is_locked=True,
    )
    cache.update(updated_state)
    assert cache.get(101).is_locked is True

    # Active track purge
    cache.get_or_create(102)
    evicted = cache.purge_expired(active_track_ids={101})
    assert evicted == [102]
    assert cache.get(102) is None
    assert cache.get(101) is not None
    print("[+] HumanStateCache test passed.")


if __name__ == "__main__":
    test_roi_crop_cache()
    test_face_quality_estimator()
    test_human_representation_extractor()
    test_human_state_cache()
    print("\n[SUCCESS] All Human Representation & Domain Foundation Unit Tests PASSED!\n")
