"""
Detection data models.

Represents a single object detection result from a model inference pass.
Each detection contains bounding box coordinates, confidence score,
class information, and optional pose keypoints.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


class DetectionClass(Enum):
    """Enumeration of detectable object classes.

    Extensible enum for all object types the framework can detect.
    New analytics modules should add their classes here.
    """

    PERSON = auto()
    VEHICLE = auto()
    # Future: PPE, FIRE, etc.


@dataclass(frozen=True, slots=True)
class BoundingBox:
    """Axis-aligned bounding box in pixel coordinates.

    Attributes:
        x1: Left edge x-coordinate.
        y1: Top edge y-coordinate.
        x2: Right edge x-coordinate.
        y2: Bottom edge y-coordinate.
    """

    x1: int
    y1: int
    x2: int
    y2: int

    @property
    def width(self) -> int:
        """Width of the bounding box in pixels."""
        return self.x2 - self.x1

    @property
    def height(self) -> int:
        """Height of the bounding box in pixels."""
        return self.y2 - self.y1

    @property
    def area(self) -> int:
        """Area of the bounding box in square pixels."""
        return self.width * self.height

    @property
    def center(self) -> tuple[int, int]:
        """Center point (cx, cy) of the bounding box."""
        return ((self.x1 + self.x2) // 2, (self.y1 + self.y2) // 2)

    @property
    def bottom_center(self) -> tuple[int, int]:
        """Bottom-center point (cx, y2) of the bounding box."""
        return ((self.x1 + self.x2) // 2, self.y2)

    @property
    def aspect_ratio(self) -> float:
        """Height-to-width aspect ratio. Returns 0.0 if width is zero."""
        if self.width == 0:
            return 0.0
        return self.height / self.width

    def contains_point(self, x: int, y: int) -> bool:
        """Check if a point (x, y) is inside this bounding box."""
        return self.x1 <= x <= self.x2 and self.y1 <= y <= self.y2

    def iou(self, other: BoundingBox) -> float:
        """Compute Intersection over Union (IoU) with another bounding box.

        Args:
            other: The other bounding box to compare against.

        Returns:
            IoU value between 0.0 and 1.0.
        """
        inter_x1 = max(self.x1, other.x1)
        inter_y1 = max(self.y1, other.y1)
        inter_x2 = min(self.x2, other.x2)
        inter_y2 = min(self.y2, other.y2)

        inter_area = max(0, inter_x2 - inter_x1) * max(0, inter_y2 - inter_y1)
        union_area = self.area + other.area - inter_area

        if union_area == 0:
            return 0.0
        return inter_area / union_area


@dataclass(frozen=True, slots=True)
class Keypoint:
    """A single pose keypoint.

    Attributes:
        x: X-coordinate in pixels.
        y: Y-coordinate in pixels.
        confidence: Detection confidence for this keypoint (0.0 to 1.0).
    """

    x: float
    y: float
    confidence: float

    @property
    def is_visible(self) -> bool:
        """Whether this keypoint is considered visible (confidence > 0.5)."""
        return self.confidence > 0.5


@dataclass(frozen=True, slots=True)
class PoseKeypoints:
    """COCO-format 17-point pose keypoints.

    Provides named access to individual body keypoints
    from a YOLO-Pose detection result.

    Attributes:
        keypoints: Tuple of 17 Keypoint instances in COCO order.
    """

    keypoints: tuple[Keypoint, ...] = field(default_factory=tuple)

    # --- COCO keypoint indices ---

    @property
    def nose(self) -> Optional[Keypoint]:
        return self._get(0)

    @property
    def left_eye(self) -> Optional[Keypoint]:
        return self._get(1)

    @property
    def right_eye(self) -> Optional[Keypoint]:
        return self._get(2)

    @property
    def left_ear(self) -> Optional[Keypoint]:
        return self._get(3)

    @property
    def right_ear(self) -> Optional[Keypoint]:
        return self._get(4)

    @property
    def left_shoulder(self) -> Optional[Keypoint]:
        return self._get(5)

    @property
    def right_shoulder(self) -> Optional[Keypoint]:
        return self._get(6)

    @property
    def left_elbow(self) -> Optional[Keypoint]:
        return self._get(7)

    @property
    def right_elbow(self) -> Optional[Keypoint]:
        return self._get(8)

    @property
    def left_wrist(self) -> Optional[Keypoint]:
        return self._get(9)

    @property
    def right_wrist(self) -> Optional[Keypoint]:
        return self._get(10)

    @property
    def left_hip(self) -> Optional[Keypoint]:
        return self._get(11)

    @property
    def right_hip(self) -> Optional[Keypoint]:
        return self._get(12)

    @property
    def left_knee(self) -> Optional[Keypoint]:
        return self._get(13)

    @property
    def right_knee(self) -> Optional[Keypoint]:
        return self._get(14)

    @property
    def left_ankle(self) -> Optional[Keypoint]:
        return self._get(15)

    @property
    def right_ankle(self) -> Optional[Keypoint]:
        return self._get(16)

    @property
    def visible_count(self) -> int:
        """Number of keypoints with confidence > 0.5."""
        return sum(1 for kp in self.keypoints if kp.is_visible)

    def _get(self, index: int) -> Optional[Keypoint]:
        """Safely retrieve a keypoint by index."""
        if index < len(self.keypoints):
            return self.keypoints[index]
        return None


@dataclass(frozen=True, slots=True)
class Detection:
    """A single object detection from one frame.

    Immutable record produced by the detection model.
    Contains the bounding box, classification, confidence,
    and optional pose keypoints.

    Attributes:
        bbox: Bounding box of the detected object.
        confidence: Model confidence score (0.0 to 1.0).
        detection_class: The class of the detected object.
        keypoints: Optional pose keypoints (for person detections).
    """

    bbox: BoundingBox
    confidence: float
    detection_class: DetectionClass
    keypoints: Optional[PoseKeypoints] = None

    @property
    def is_person(self) -> bool:
        """Whether this detection is a person."""
        return self.detection_class == DetectionClass.PERSON

    @property
    def has_pose(self) -> bool:
        """Whether this detection includes pose keypoints."""
        return self.keypoints is not None and len(self.keypoints.keypoints) > 0

    @property
    def ground_point(self) -> tuple[float, float]:
        """Estimated ground/feet point (x, y) for zone analytics and positioning.

        Hierarchical logic:
            1. Average of both ankles if both are visible (confidence > 0.5).
            2. Left ankle if only left ankle is visible.
            3. Right ankle if only right ankle is visible.
            4. Fallback: Bottom-center of the bounding box.
        """
        if self.keypoints is not None:
            left_ankle = self.keypoints.left_ankle
            right_ankle = self.keypoints.right_ankle

            left_valid = left_ankle is not None and left_ankle.is_visible
            right_valid = right_ankle is not None and right_ankle.is_visible

            if left_valid and right_valid:
                return (
                    (left_ankle.x + right_ankle.x) / 2.0,
                    (left_ankle.y + right_ankle.y) / 2.0,
                )
            elif left_valid:
                return (float(left_ankle.x), float(left_ankle.y))
            elif right_valid:
                return (float(right_ankle.x), float(right_ankle.y))

        # Fallback: bottom-center of bounding box
        bc = self.bbox.bottom_center
        return (float(bc[0]), float(bc[1]))
