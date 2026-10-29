"""
Unit tests for face detection survey helper functions.

Tests width bucketing, score bucketing, and crop boundary safety using
pure synthetic inputs without requiring model weights or real face images.
"""

from __future__ import annotations

import numpy as np
import pytest

from camera_analytics.scripts.face_detect_survey import (
    compute_score_buckets,
    compute_width_buckets,
    extract_face_crop,
)


class TestFaceDetectSurveyBucketing:
    """Test synthetic bucketing functions for widths and scores."""

    def test_compute_width_buckets_synthetic_counts(self) -> None:
        widths = [25.0, 40.0, 50.0, 64.0, 75.0, 80.0, 100.0, 112.0, 150.0]
        buckets = compute_width_buckets(widths)

        assert buckets["w_gte_40"] == 8
        assert buckets["w_gte_64"] == 6
        assert buckets["w_gte_80"] == 4
        assert buckets["w_gte_112"] == 2

    def test_compute_width_buckets_empty_list(self) -> None:
        buckets = compute_width_buckets([])
        assert buckets == {
            "w_gte_40": 0,
            "w_gte_64": 0,
            "w_gte_80": 0,
            "w_gte_112": 0,
        }

    def test_compute_width_buckets_all_small(self) -> None:
        widths = [10.0, 20.0, 35.0, 39.9]
        buckets = compute_width_buckets(widths)
        assert buckets["w_gte_40"] == 0
        assert buckets["w_gte_64"] == 0
        assert buckets["w_gte_80"] == 0
        assert buckets["w_gte_112"] == 0

    def test_compute_score_buckets_synthetic_counts(self) -> None:
        scores = [0.55, 0.60, 0.75, 0.80, 0.85, 0.90, 0.99]
        buckets = compute_score_buckets(scores)

        assert buckets["score_gte_0_6"] == 6
        assert buckets["score_gte_0_8"] == 4
        assert buckets["score_gte_0_9"] == 2


class TestExtractFaceCrop:
    """Test geometric face crop extraction with synthetic arrays."""

    def test_crop_normal_coordinates(self) -> None:
        canvas = np.zeros((200, 200, 3), dtype=np.uint8)
        canvas[50:100, 40:110] = 255
        crop = extract_face_crop(canvas, x=40, y=50, w=70, h=50)

        assert crop.shape == (50, 70, 3)
        assert np.all(crop == 255)

    def test_crop_clips_to_canvas_boundaries(self) -> None:
        canvas = np.zeros((100, 100, 3), dtype=np.uint8)
        # Bounding box exceeding image dimensions
        crop = extract_face_crop(canvas, x=80, y=80, w=50, h=50)

        # Clamped to [80:100, 80:100] -> (20, 20, 3)
        assert crop.shape == (20, 20, 3)

    def test_crop_negative_coordinates(self) -> None:
        canvas = np.zeros((100, 100, 3), dtype=np.uint8)
        crop = extract_face_crop(canvas, x=-20, y=-20, w=50, h=50)
        # Clamped to [0:30, 0:30]
        assert crop.shape == (30, 30, 3)

