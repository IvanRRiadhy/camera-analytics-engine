"""
Face Embedder Interface and SFace Implementation using OpenCV FaceRecognizerSF.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Tuple, Union

import cv2
import numpy as np

from camera_analytics.plugins.face_matching.detector import FaceDetection

logger = logging.getLogger(__name__)


class BaseFaceEmbedder(ABC):
    """Abstract interface for face feature embedding and metric alignment.

    Allows plugging in SFace, ArcFace, or other embedding architectures seamlessly.
    """

    @abstractmethod
    def align(self, frame: np.ndarray, face: Union[FaceDetection, np.ndarray]) -> np.ndarray:
        """Align and crop face into canonical coordinate frame using 5 landmarks.

        Args:
            frame: Raw BGR input frame (H, W, 3).
            face: FaceDetection instance or 15-element raw face parameter array.

        Returns:
            Aligned and cropped face image array (H, W, 3).
        """
        pass

    @abstractmethod
    def embed(self, frame: np.ndarray, face: Union[FaceDetection, np.ndarray]) -> np.ndarray:
        """Extract L2-normalized feature embedding vector from detected or aligned face.

        Args:
            frame: Raw BGR input frame (H, W, 3).
            face: FaceDetection instance, raw face array, or pre-aligned face image.

        Returns:
            1D float32 numpy array with unit L2-norm (||v||_2 = 1.0).
        """
        pass

    @abstractmethod
    def embed_aligned(self, aligned_face: np.ndarray) -> np.ndarray:
        """Extract L2-normalized feature embedding vector from an already aligned face crop.

        Args:
            aligned_face: Canonical aligned face image (H, W, 3).

        Returns:
            1D float32 numpy array with unit L2-norm.
        """
        pass

    @staticmethod
    def compute_similarity(embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """Compute cosine similarity between two feature embeddings.

        Args:
            embedding1: First 1D feature embedding vector.
            embedding2: Second 1D feature embedding vector.

        Returns:
            Cosine similarity score in [-1.0, 1.0].
        """
        e1 = np.asarray(embedding1, dtype=np.float32).flatten()
        e2 = np.asarray(embedding2, dtype=np.float32).flatten()
        norm1 = float(np.linalg.norm(e1))
        norm2 = float(np.linalg.norm(e2))
        if norm1 < 1e-9 or norm2 < 1e-9:
            return 0.0
        similarity = float(np.dot(e1, e2) / (norm1 * norm2))
        return float(np.clip(similarity, -1.0, 1.0))


class SFaceEmbedder(BaseFaceEmbedder):
    """Deep face feature embedder using OpenCV cv2.FaceRecognizerSF (SFace 128-D)."""

    FEATURE_DIM: int = 128
    CANONICAL_SIZE: Tuple[int, int] = (112, 112)

    def __init__(
        self,
        model_path: Union[str, Path],
        backend_id: int = cv2.dnn.DNN_BACKEND_OPENCV,
        target_id: int = cv2.dnn.DNN_TARGET_CPU,
    ) -> None:
        """Initialize SFace face feature recognizer.

        Args:
            model_path: Path to the SFace ONNX model file.
            backend_id: OpenCV DNN backend identifier (default: DNN_BACKEND_OPENCV).
            target_id: OpenCV DNN target device identifier (default: DNN_TARGET_CPU).

        Raises:
            FileNotFoundError: If the model file does not exist at model_path.
            ValueError: If OpenCV lacks FaceRecognizerSF support.
        """
        if not hasattr(cv2, "FaceRecognizerSF"):
            raise ValueError("OpenCV installation lacks FaceRecognizerSF support.")

        path = Path(model_path).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"SFace face recognizer weights not found at: {path}")

        self.model_path = path
        self.backend_id = backend_id
        self.target_id = target_id

        self._recognizer = cv2.FaceRecognizerSF.create(
            model=str(self.model_path),
            config="",
            backend_id=self.backend_id,
            target_id=self.target_id,
        )

    def align(self, frame: np.ndarray, face: Union[FaceDetection, np.ndarray]) -> np.ndarray:
        """Align and crop face using 5 facial landmarks to 112x112 canonical resolution.

        Args:
            frame: Input BGR image (H, W, 3).
            face: FaceDetection instance or 15-element raw face parameter array.

        Returns:
            112x112 aligned face image in BGR uint8 format.
        """
        raw_face = face.raw_face if isinstance(face, FaceDetection) else np.asarray(face, dtype=np.float32)
        if raw_face.ndim > 1:
            raw_face = raw_face.flatten()

        aligned: np.ndarray = self._recognizer.alignCrop(frame, raw_face)
        return aligned

    def embed(self, frame: np.ndarray, face: Union[FaceDetection, np.ndarray]) -> np.ndarray:
        """Extract L2-normalized 128-D feature embedding vector.

        If face is already an aligned 112x112 image, embeds it directly;
        otherwise aligns and extracts features.

        Args:
            frame: Input BGR image.
            face: FaceDetection instance, raw face array, or pre-aligned 112x112 face image.

        Returns:
            Unit-norm 128-D float32 numpy array.
        """
        # Check if face is already an aligned crop
        if isinstance(face, np.ndarray) and face.shape[:2] == self.CANONICAL_SIZE and face.ndim == 3:
            aligned = face
        else:
            aligned = self.align(frame, face)

        return self.embed_aligned(aligned)

    def embed_aligned(self, aligned_face: np.ndarray) -> np.ndarray:
        """Extract L2-normalized 128-D feature vector from aligned 112x112 face crop.

        Args:
            aligned_face: Pre-aligned (112, 112, 3) BGR face image.

        Returns:
            Unit-norm 128-D float32 numpy array (||v||_2 = 1.0).
        """
        if aligned_face is None or aligned_face.size == 0:
            raise ValueError("aligned_face cannot be empty.")

        feature: np.ndarray = self._recognizer.feature(aligned_face)
        feature_1d = feature.flatten().astype(np.float32)

        # L2-normalization
        norm = float(np.linalg.norm(feature_1d))
        if norm > 1e-9:
            feature_1d = feature_1d / norm
        else:
            feature_1d = np.zeros(self.FEATURE_DIM, dtype=np.float32)

        return feature_1d

