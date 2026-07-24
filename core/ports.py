"""
Ports for AI model integration.

Defines abstract interfaces (ports) for object detection and tracking.
Concrete adapters (e.g., YOLOPoseAdapter, BoTSORTAdapter) implement
these interfaces, keeping the framework core decoupled from any
specific AI model or tracking algorithm.

This follows the Ports & Adapters (Hexagonal Architecture) pattern:
    - Port = interface defined here (what the framework expects)
    - Adapter = concrete implementation (how a specific model delivers it)

The adapters will be implemented in a future sprint when integrating
YOLO and BoT-SORT. For now, only the interfaces are defined.

Example future usage::

    class YOLOPoseAdapter(DetectorPort):
        def __init__(self, model_path: str, device: str = "cuda"):
            self._model = YOLO(model_path)
            ...

        def detect(self, frame: NDArray) -> DetectionResult:
            results = self._model(frame)
            detections = self._convert(results)
            return DetectionResult(detections=detections, ...)

    class BoTSORTAdapter(TrackerPort):
        def track(self, frame, det_result) -> TrackingResult:
            ...
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

import numpy as np

from camera_analytics.core.detection_set import DetectionSet
from camera_analytics.core.track_manager import TrackerResult
from camera_analytics.models.detection import Detection

if TYPE_CHECKING:
    from numpy.typing import NDArray


@dataclass(frozen=True, slots=True)
class DetectionResult:
    """Output from a detection model for one frame.

    Wraps the raw detection list into a structured result with
    model metadata. This is the return type of DetectorPort.detect().

    Attributes:
        detections: DetectionSet containing all detections.
        model_name: Name of the model that produced the detections.
        inference_time_ms: Model inference time in milliseconds.
        metadata: Additional model-specific metadata.
    """

    detections: DetectionSet
    model_name: str = ""
    inference_time_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def count(self) -> int:
        """Number of detections."""
        return len(self.detections)

    @property
    def is_empty(self) -> bool:
        """Whether no objects were detected."""
        return self.detections.is_empty


@dataclass(frozen=True, slots=True)
class TrackingResult:
    """Output from a tracking algorithm for one frame.

    Wraps the tracker output into a structured result. This is
    the return type of TrackerPort.track().

    Attributes:
        results: List of TrackerResult (track_id + detection pairs).
        tracker_name: Name of the tracking algorithm.
        inference_time_ms: Tracking inference time in milliseconds.
        metadata: Additional tracker-specific metadata.
    """

    results: list[TrackerResult]
    tracker_name: str = ""
    inference_time_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def count(self) -> int:
        """Number of tracked objects."""
        return len(self.results)

    @property
    def track_ids(self) -> list[int]:
        """List of all track IDs in this result."""
        return [r.track_id for r in self.results]

    @property
    def new_tracks(self) -> list[TrackerResult]:
        """Tracker results flagged as newly created tracks."""
        return [r for r in self.results if r.is_new]


class DetectorPort(ABC):
    """Abstract interface for object detection models.

    Any detection model (YOLO, RT-DETR, etc.) must implement this
    interface to integrate with the framework. The Pipeline calls
    detect() each frame and receives a DetectionResult.

    Implementing a detector::

        class YOLOPoseAdapter(DetectorPort):

            @property
            def name(self) -> str:
                return "yolo_pose_v8"

            def load(self, model_path: str, device: str = "cuda") -> None:
                self._model = YOLO(model_path)
                self._model.to(device)

            def detect(self, frame: NDArray[np.uint8]) -> DetectionResult:
                results = self._model(frame, verbose=False)
                detections = self._parse_results(results)
                return DetectionResult(
                    detections=DetectionSet(detections),
                    model_name=self.name,
                )

            def release(self) -> None:
                del self._model
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of the detector model.

        Returns:
            Model name string (e.g., 'yolo_pose_v8', 'rt_detr').
        """

    @abstractmethod
    def load(self, model_path: str, device: str = "cuda") -> None:
        """Load the detection model.

        Args:
            model_path: Path to the model weights file.
            device: Compute device ('cuda', 'cpu', 'mps').
        """

    @abstractmethod
    def detect(self, frame: NDArray[np.uint8]) -> DetectionResult:
        """Run detection on a single frame.

        Args:
            frame: BGR image as HxWx3 uint8 numpy array.

        Returns:
            DetectionResult containing all detections.
        """

    @abstractmethod
    def release(self) -> None:
        """Release model resources (GPU memory, etc.)."""

    def warmup(self, frame_shape: tuple[int, int, int] = (1080, 1920, 3)) -> None:
        """Optional warmup pass to initialize GPU kernels.

        Default implementation runs one detection on a blank frame.

        Args:
            frame_shape: Shape of the warmup frame (H, W, C).
        """
        dummy = np.zeros(frame_shape, dtype=np.uint8)
        self.detect(dummy)


class TrackerPort(ABC):
    """Abstract interface for object tracking algorithms.

    Any tracker (BoT-SORT, ByteTrack, DeepSORT, etc.) must implement
    this interface. The Pipeline calls track() each frame with the
    detection results and receives a TrackingResult.

    Implementing a tracker::

        class BoTSORTAdapter(TrackerPort):

            @property
            def name(self) -> str:
                return "botsort"

            def initialize(self, config) -> None:
                self._tracker = BoTSORT(config)

            def track(self, frame, det_result) -> TrackingResult:
                tracker_output = self._tracker.update(
                    frame, det_result.detections
                )
                results = [
                    TrackerResult(track_id=t.id, detection=t.det)
                    for t in tracker_output
                ]
                return TrackingResult(
                    results=results,
                    tracker_name=self.name,
                )

            def reset(self) -> None:
                self._tracker.reset()
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of the tracking algorithm.

        Returns:
            Tracker name string (e.g., 'botsort', 'bytetrack').
        """

    @abstractmethod
    def initialize(self, config: Optional[dict[str, Any]] = None) -> None:
        """Initialize the tracker.

        Args:
            config: Optional tracker-specific configuration.
        """

    @abstractmethod
    def track(
        self,
        frame: NDArray[np.uint8],
        detection_result: DetectionResult,
    ) -> TrackingResult:
        """Run tracking on a frame with detections.

        Associates detections with existing tracks, creates new
        tracks, and marks lost tracks.

        Args:
            frame: BGR image as HxWx3 uint8 numpy array.
            detection_result: Detection output from DetectorPort.

        Returns:
            TrackingResult with track_id ↔ detection associations.
        """

    @abstractmethod
    def reset(self) -> None:
        """Reset the tracker state (clear all internal tracks)."""
