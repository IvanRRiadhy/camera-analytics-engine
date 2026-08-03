"""
Fake detector adapter.

A synthetic implementation of DetectorPort for testing and
development. Generates configurable fake person detections
without any AI model or GPU.

Use this to verify the full pipeline flow (detect → track →
process) without loading YOLO or any real model.

Example::

    detector = FakeDetector(person_count=3, confidence_range=(0.7, 0.95))
    detector.load("not_used")

    det_result = detector.detect(frame)
    print(det_result.count)  # 3
    print(det_result.detections.persons().count)  # 3
"""

from __future__ import annotations

import logging
import random
import time
from typing import TYPE_CHECKING

import numpy as np

from camera_analytics.core.detection_set import DetectionSet
from camera_analytics.core.ports import DetectionResult, DetectorPort
from camera_analytics.models.detection import (
    BoundingBox,
    Detection,
    DetectionClass,
    Keypoint,
    PoseKeypoints,
)

if TYPE_CHECKING:
    from numpy.typing import NDArray

logger = logging.getLogger(__name__)


# COCO pose keypoint names (17 keypoints)
_POSE_KEYPOINT_NAMES: tuple[str, ...] = (
    "nose",
    "left_eye",
    "right_eye",
    "left_ear",
    "right_ear",
    "left_shoulder",
    "right_shoulder",
    "left_elbow",
    "right_elbow",
    "left_wrist",
    "right_wrist",
    "left_hip",
    "right_hip",
    "left_knee",
    "right_knee",
    "left_ankle",
    "right_ankle",
)


class FakeDetector(DetectorPort):
    """Synthetic detector that generates fake person detections.

    Produces a configurable number of person detections with
    randomized bounding boxes, confidences, and optional pose
    keypoints. No AI model is loaded.

    Args:
        person_count: Number of person detections per frame.
        confidence_range: Tuple of (min, max) confidence values.
        generate_pose: Whether to generate fake pose keypoints.
        seed: Optional random seed for reproducible output.

    Example::

        detector = FakeDetector(person_count=5, generate_pose=True)
        detector.load("unused")

        result = detector.detect(frame)
        for det in result.detections.persons():
            print(det.bbox, det.confidence, len(det.keypoints))
    """

    def __init__(
        self,
        person_count: int = 3,
        confidence_range: tuple[float, float] = (0.65, 0.95),
        generate_pose: bool = True,
        seed: int | None = None,
    ) -> None:
        self._person_count = person_count
        self._confidence_range = confidence_range
        self._generate_pose = generate_pose
        self._rng = random.Random(seed)
        self._loaded = False
        self._frame_width = 1920
        self._frame_height = 1080

    @property
    def name(self) -> str:
        """Detector name."""
        return "fake_detector"

    def load(self, model_path: str, device: str = "cpu") -> None:
        """Simulate model loading.

        Args:
            model_path: Ignored (no real model).
            device: Ignored (no GPU needed).
        """
        self._loaded = True
        logger.info(
            "FakeDetector loaded (persons=%d, pose=%s, conf=%.2f-%.2f)",
            self._person_count,
            self._generate_pose,
            *self._confidence_range,
        )

    def detect(self, frame: NDArray[np.uint8]) -> DetectionResult:
        """Generate fake detections for the given frame.

        Args:
            frame: Video frame (used only for dimensions).

        Returns:
            DetectionResult with synthetic person detections.

        Raises:
            RuntimeError: If load() has not been called.
        """
        if not self._loaded:
            raise RuntimeError(
                "FakeDetector.load() must be called before detect()."
            )

        start = time.perf_counter()

        h, w = frame.shape[:2]
        self._frame_width = w
        self._frame_height = h

        detections = [
            self._generate_person(i, w, h)
            for i in range(self._person_count)
        ]

        elapsed_ms = (time.perf_counter() - start) * 1000

        return DetectionResult(
            detections=DetectionSet(detections),
            model_name=self.name,
            inference_time_ms=elapsed_ms,
        )

    def release(self) -> None:
        """Release resources (no-op for fake detector)."""
        self._loaded = False
        logger.info("FakeDetector released")

    def set_person_count(self, count: int) -> None:
        """Change the number of people generated per frame.

        Useful for simulating changing crowd conditions.

        Args:
            count: New person count.
        """
        self._person_count = count

    # --- Internal ---

    def _generate_person(
        self, index: int, frame_w: int, frame_h: int
    ) -> Detection:
        """Generate a single fake person detection.

        Creates a plausible bounding box position based on the
        person's index, with randomized size and confidence.

        Args:
            index: Person index (for spatial distribution).
            frame_w: Frame width in pixels.
            frame_h: Frame height in pixels.

        Returns:
            A Detection object with PERSON class.
        """
        # Distribute people across the frame horizontally
        spacing = frame_w // max(self._person_count + 1, 2)
        center_x = spacing * (index + 1)
        center_y = frame_h // 2 + self._rng.randint(-100, 100)

        # Randomized person dimensions (realistic proportions)
        person_w = self._rng.randint(50, 100)
        person_h = self._rng.randint(120, 250)

        x1 = max(0, center_x - person_w // 2)
        y1 = max(0, center_y - person_h // 2)
        x2 = min(frame_w, x1 + person_w)
        y2 = min(frame_h, y1 + person_h)

        bbox = BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2)

        confidence = self._rng.uniform(*self._confidence_range)

        # Optional pose keypoints
        keypoints: PoseKeypoints | None = None
        if self._generate_pose:
            keypoints = PoseKeypoints(keypoints=tuple(self._generate_keypoints(bbox)))

        return Detection(
            bbox=bbox,
            confidence=round(confidence, 4),
            detection_class=DetectionClass.PERSON,
            keypoints=keypoints,
        )

    def _generate_keypoints(self, bbox: BoundingBox) -> list[Keypoint]:
        """Generate fake COCO pose keypoints within a bounding box.

        Places 17 keypoints at approximate anatomical positions
        relative to the bounding box.

        Args:
            bbox: The person's bounding box.

        Returns:
            List of 17 Keypoint objects.
        """
        cx, cy = bbox.center
        bw = bbox.width
        bh = bbox.height

        # Approximate keypoint positions relative to bbox
        # (x_ratio, y_ratio) from top-left of bbox
        ratios: list[tuple[float, float]] = [
            (0.50, 0.08),   # nose
            (0.45, 0.05),   # left_eye
            (0.55, 0.05),   # right_eye
            (0.38, 0.07),   # left_ear
            (0.62, 0.07),   # right_ear
            (0.30, 0.22),   # left_shoulder
            (0.70, 0.22),   # right_shoulder
            (0.22, 0.40),   # left_elbow
            (0.78, 0.40),   # right_elbow
            (0.18, 0.55),   # left_wrist
            (0.82, 0.55),   # right_wrist
            (0.35, 0.58),   # left_hip
            (0.65, 0.58),   # right_hip
            (0.32, 0.76),   # left_knee
            (0.68, 0.76),   # right_knee
            (0.30, 0.95),   # left_ankle
            (0.70, 0.95),   # right_ankle
        ]

        keypoints: list[Keypoint] = []
        for i, (rx, ry) in enumerate(ratios):
            # Add slight randomness
            jitter_x = self._rng.randint(-3, 3)
            jitter_y = self._rng.randint(-3, 3)

            kp_x = int(bbox.x1 + bw * rx) + jitter_x
            kp_y = int(bbox.y1 + bh * ry) + jitter_y

            keypoints.append(
                Keypoint(
                    x=float(kp_x),
                    y=float(kp_y),
                    confidence=self._rng.uniform(0.5, 0.99),
                )
            )

        return keypoints
