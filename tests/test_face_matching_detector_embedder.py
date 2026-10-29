"""
Unit tests for Face Matching detector (YuNet) and embedder (SFace).

Tests cover synthetic inputs, error handling on missing weights, unit-norm output,
and cosine similarity invariants. Tests requiring ONNX models are skipped if weights
are absent.
"""

from __future__ import annotations

from pathlib import Path
import cv2
import numpy as np
import pytest

from camera_analytics.plugins.face_matching.detector import FaceDetection, YuNetDetector
from camera_analytics.plugins.face_matching.embedder import BaseFaceEmbedder, SFaceEmbedder

REPO_ROOT = Path(__file__).resolve().parent.parent
YUNET_WEIGHTS = REPO_ROOT / "models" / "face" / "face_detection_yunet_2023mar.onnx"
SFACE_WEIGHTS = REPO_ROOT / "models" / "face" / "face_recognition_sface_2021dec.onnx"


class TestFaceDetectorEmbedderErrors:
    """Error handling tests with non-existent or invalid models."""

    def test_detector_missing_weights_raises_file_not_found(self, tmp_path: Path) -> None:
        missing_path = tmp_path / "non_existent_yunet.onnx"
        with pytest.raises(FileNotFoundError, match="YuNet face detector weights not found"):
            YuNetDetector(missing_path)

    def test_embedder_missing_weights_raises_file_not_found(self, tmp_path: Path) -> None:
        missing_path = tmp_path / "non_existent_sface.onnx"
        with pytest.raises(FileNotFoundError, match="SFace face recognizer weights not found"):
            SFaceEmbedder(missing_path)


class TestFaceDetectorSynthetic:
    """Tests for YuNetDetector using synthetic frames."""

    @pytest.mark.skipif(not YUNET_WEIGHTS.is_file(), reason="YuNet weights face_detection_yunet_2023mar.onnx not found")
    def test_detector_returns_empty_list_on_blank_frame(self) -> None:
        detector = YuNetDetector(YUNET_WEIGHTS)
        blank = np.zeros((320, 320, 3), dtype=np.uint8)
        faces = detector.detect(blank)
        assert isinstance(faces, list)
        assert len(faces) == 0

    @pytest.mark.skipif(not YUNET_WEIGHTS.is_file(), reason="YuNet weights face_detection_yunet_2023mar.onnx not found")
    def test_detector_handles_empty_or_invalid_inputs(self) -> None:
        detector = YuNetDetector(YUNET_WEIGHTS)
        assert detector.detect(None) == []  # type: ignore[arg-type]
        assert detector.detect(np.array([])) == []
        assert detector.detect(np.zeros((0, 0, 3), dtype=np.uint8)) == []


class TestFaceEmbedderSynthetic:
    """Tests for SFaceEmbedder using synthetic inputs and mathematical invariants."""

    @pytest.mark.skipif(not SFACE_WEIGHTS.is_file(), reason="SFace weights face_recognition_sface_2021dec.onnx not found")
    def test_embedder_returns_unit_norm_128d(self) -> None:
        embedder = SFaceEmbedder(SFACE_WEIGHTS)
        # Create a deterministic synthetic 112x112 aligned face crop
        rng = np.random.default_rng(42)
        synth_crop = rng.integers(0, 255, (112, 112, 3), dtype=np.uint8)

        embedding = embedder.embed_aligned(synth_crop)

        assert isinstance(embedding, np.ndarray)
        assert embedding.shape == (128,)
        assert embedding.dtype == np.float32
        # Check unit L2-norm: ||v||_2 == 1.0 within numerical precision
        l2_norm = float(np.linalg.norm(embedding))
        assert abs(l2_norm - 1.0) < 1e-5

    @pytest.mark.skipif(not SFACE_WEIGHTS.is_file(), reason="SFace weights face_recognition_sface_2021dec.onnx not found")
    def test_identical_image_cosine_similarity_is_one(self) -> None:
        embedder = SFaceEmbedder(SFACE_WEIGHTS)
        rng = np.random.default_rng(101)
        synth_crop = rng.integers(0, 255, (112, 112, 3), dtype=np.uint8)

        emb1 = embedder.embed_aligned(synth_crop)
        emb2 = embedder.embed_aligned(synth_crop.copy())

        cosine_sim = BaseFaceEmbedder.compute_similarity(emb1, emb2)
        assert isinstance(cosine_sim, float)
        assert abs(cosine_sim - 1.0) < 1e-4

    @pytest.mark.skipif(not SFACE_WEIGHTS.is_file(), reason="SFace weights face_recognition_sface_2021dec.onnx not found")
    def test_embedder_align_and_embed_pipeline(self) -> None:
        embedder = SFaceEmbedder(SFACE_WEIGHTS)
        frame = np.zeros((300, 300, 3), dtype=np.uint8)

        # Synthetic FaceDetection with reasonable coordinates
        raw_face = np.array(
            [50, 50, 100, 100, 80, 80, 120, 80, 100, 100, 85, 130, 115, 130, 0.95],
            dtype=np.float32,
        )
        detection = FaceDetection(
            box=(50.0, 50.0, 100.0, 100.0),
            landmarks=[(80.0, 80.0), (120.0, 80.0), (100.0, 100.0), (85.0, 130.0), (115.0, 130.0)],
            score=0.95,
            raw_face=raw_face,
        )

        aligned = embedder.align(frame, detection)
        assert aligned.shape == (112, 112, 3)

        embedding = embedder.embed(frame, detection)
        assert embedding.shape == (128,)
        assert abs(float(np.linalg.norm(embedding)) - 1.0) < 1e-5


class TestSimilarityMetric:
    """Pure mathematical test for BaseFaceEmbedder.compute_similarity."""

    def test_similarity_orthogonal_and_opposite(self) -> None:
        e1 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        e2 = np.array([0.0, 1.0, 0.0], dtype=np.float32)
        e3 = np.array([-1.0, 0.0, 0.0], dtype=np.float32)

        assert abs(BaseFaceEmbedder.compute_similarity(e1, e2)) < 1e-6
        assert abs(BaseFaceEmbedder.compute_similarity(e1, e3) - (-1.0)) < 1e-6
        assert abs(BaseFaceEmbedder.compute_similarity(e1, e1) - 1.0) < 1e-6

    def test_similarity_zero_vector_returns_zero(self) -> None:
        e1 = np.zeros(128, dtype=np.float32)
        e2 = np.ones(128, dtype=np.float32)
        assert BaseFaceEmbedder.compute_similarity(e1, e2) == 0.0

