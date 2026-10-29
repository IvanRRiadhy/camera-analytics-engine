"""
YuNet Face Detector Implementation using OpenCV FaceDetectorYN.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional, Tuple, Union

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class FaceDetection:
    """Detected face representation containing bounding box, landmarks, and confidence.

    Attributes:
        box: (x, y, w, h) bounding box coordinates in pixels.
        landmarks: List of 5 landmark (x, y) coordinates:
            [right_eye, left_eye, nose_tip, right_mouth_corner, left_mouth_corner].
        score: Face detection confidence score in [0.0, 1.0].
        raw_face: Underlying 15-element float array formatted for OpenCV FaceRecognizerSF.
    """

    box: Tuple[float, float, float, float]
    landmarks: List[Tuple[float, float]]
    score: float
    raw_face: np.ndarray = field(default_factory=lambda: np.zeros(15, dtype=np.float32))

    @property
    def x(self) -> float:
        """Left coordinate."""
        return self.box[0]

    @property
    def y(self) -> float:
        """Top coordinate."""
        return self.box[1]

    @property
    def w(self) -> float:
        """Bounding box width."""
        return self.box[2]

    @property
    def h(self) -> float:
        """Bounding box height."""
        return self.box[3]

    @property
    def x1(self) -> float:
        """Top-left x coordinate."""
        return self.box[0]

    @property
    def y1(self) -> float:
        """Top-left y coordinate."""
        return self.box[1]

    @property
    def x2(self) -> float:
        """Bottom-right x coordinate."""
        return self.box[0] + self.box[2]

    @property
    def y2(self) -> float:
        """Bottom-right y coordinate."""
        return self.box[1] + self.box[3]

    @property
    def bbox(self) -> List[float]:
        """Return [x1, y1, x2, y2] standard bounding box representation."""
        return [self.x1, self.y1, self.x2, self.y2]


class YuNetDetector:
    """High-performance edge face detector using OpenCV cv2.FaceDetectorYN (YuNet)."""

    def __init__(
        self,
        model_path: Union[str, Path],
        score_threshold: float = 0.6,
        nms_threshold: float = 0.3,
        top_k: int = 5000,
        backend_id: int = cv2.dnn.DNN_BACKEND_OPENCV,
        target_id: int = cv2.dnn.DNN_TARGET_CPU,
    ) -> None:
        """Initialize YuNet face detector.

        Args:
            model_path: Path to the YuNet ONNX model file.
            score_threshold: Minimum detection confidence threshold (default: 0.6).
            nms_threshold: Non-Maximum Suppression threshold (default: 0.3).
            top_k: Maximum number of detections to keep before NMS (default: 5000).
            backend_id: OpenCV DNN backend identifier (default: DNN_BACKEND_OPENCV).
            target_id: OpenCV DNN target device identifier (default: DNN_TARGET_CPU).

        Raises:
            FileNotFoundError: If the model file does not exist at model_path.
            ValueError: If OpenCV lacks FaceDetectorYN support.
        """
        if not hasattr(cv2, "FaceDetectorYN"):
            raise ValueError("OpenCV installation lacks FaceDetectorYN support.")

        path = Path(model_path).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"YuNet face detector weights not found at: {path}")

        self.model_path = path
        self.score_threshold = float(score_threshold)
        self.nms_threshold = float(nms_threshold)
        self.top_k = int(top_k)
        self.backend_id = backend_id
        self.target_id = target_id

        # Internal detector instance
        self._detector = cv2.FaceDetectorYN.create(
            model=str(self.model_path),
            config="",
            input_size=(320, 320),
            score_threshold=self.score_threshold,
            nms_threshold=self.nms_threshold,
            top_k=self.top_k,
            backend_id=self.backend_id,
            target_id=self.target_id,
        )
        self._current_input_size: Tuple[int, int] = (320, 320)

    def detect(self, frame: np.ndarray) -> List[FaceDetection]:
        """Detect faces in a BGR image frame.

        Args:
            frame: Input image array (H, W, 3) in uint8 BGR format.

        Returns:
            List of FaceDetection objects, or empty list if no faces are detected.
        """
        if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0 or frame.ndim < 2:
            return []

        h, w = frame.shape[:2]
        if (w, h) != self._current_input_size:
            self._detector.setInputSize((w, h))
            self._current_input_size = (w, h)

        retval, faces = self._detector.detect(frame)
        if faces is None or retval == 0 or len(faces) == 0:
            return []

        detections: List[FaceDetection] = []
        for row in faces:
            box = (float(row[0]), float(row[1]), float(row[2]), float(row[3]))
            landmarks = [
                (float(row[4 + 2 * j]), float(row[5 + 2 * j]))
                for j in range(5)
            ]
            score = float(row[14])
            detections.append(
                FaceDetection(
                    box=box,
                    landmarks=landmarks,
                    score=score,
                    raw_face=np.asarray(row, dtype=np.float32),
                )
            )

        return detections

