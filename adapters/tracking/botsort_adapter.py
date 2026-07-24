"""
BoT-SORT tracker adapter implementation.

Concrete implementation of TrackerPort for the BoT-SORT multi-object tracking algorithm.
Isolates all external tracking library dependencies inside this adapter.
Converts raw tracking outputs into framework-native TrackingResult and TrackerResult objects.

Features:
    - Lazy loading of external tracking dependencies with fallback matching.
    - Association of tracking outputs with original Detection objects (preserving 17 COCO pose keypoints & ground_point).
    - Maintenance of persistent track IDs and state flags (`is_new`).
    - Logging of track creation, confirmation, loss, and re-association events.
    - Zero leaks of internal tracker objects outside the adapter.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional

import numpy as np

from camera_analytics.core.ports import DetectionResult, TrackerPort, TrackingResult
from camera_analytics.core.track_manager import TrackerResult
from camera_analytics.models.detection import BoundingBox, Detection, DetectionClass

if TYPE_CHECKING:
    from numpy.typing import NDArray

logger = logging.getLogger(__name__)


@dataclass
class _InternalTrackState:
    """Internal track state for nearest-neighbor fallback association when external tracker is absent.

    Attributes:
        track_id: Assigned persistent integer ID.
        last_detection: Most recent matched Detection.
        miss_count: Consecutive frames without a match.
    """

    track_id: int
    last_detection: Detection
    miss_count: int = 0


class BoTSORTAdapter(TrackerPort):
    """Adapter for BoT-SORT (or compatible ByteTrack/BoTSORT) tracking algorithms.

    Converts raw tracker outputs into framework-native TrackerResult objects.
    Ensures pose keypoints and ground_point attributes from original detections
    are preserved on assigned tracks.

    Args:
        track_high_thresh: High confidence threshold for tracking association.
        track_low_thresh: Low confidence threshold for tracking association.
        new_track_thresh: Confidence threshold required to activate a new track.
        track_buffer: Number of frames to buffer lost tracks before removal.
        match_thresh: Matching IoU/distance threshold for data association.
    """

    def __init__(
        self,
        track_high_thresh: float = 0.5,
        track_low_thresh: float = 0.1,
        new_track_thresh: float = 0.6,
        track_buffer: int = 30,
        match_thresh: float = 0.8,
    ) -> None:
        self._track_high_thresh = track_high_thresh
        self._track_low_thresh = track_low_thresh
        self._new_track_thresh = new_track_thresh
        self._track_buffer = track_buffer
        self._match_thresh = match_thresh

        self._tracker: Any = None
        self._initialized: bool = False
        self._uses_fallback: bool = False

        # Fallback internal state
        self._internal_tracks: list[_InternalTrackState] = []
        self._next_id: int = 1

    @property
    def name(self) -> str:
        """Tracker name."""
        return "botsort"

    @property
    def is_initialized(self) -> bool:
        """Whether the tracker is initialized and ready for tracking."""
        return self._initialized

    def initialize(self, config: Optional[dict[str, Any]] = None) -> None:
        """Initialize the BoT-SORT tracker instance.

        Performs lazy import of tracking library dependencies (e.g., `boxmot` or `ultralytics.trackers`).
        If external tracking libraries are absent, initializes fallback data association cleanly.

        Args:
            config: Optional configuration overrides.
        """
        if config:
            self._track_high_thresh = float(config.get("track_high_thresh", self._track_high_thresh))
            self._track_low_thresh = float(config.get("track_low_thresh", self._track_low_thresh))
            self._track_buffer = int(config.get("track_buffer", self._track_buffer))
            self._match_thresh = float(config.get("match_thresh", self._match_thresh))

        # Attempt to initialize external BoT-SORT tracker if available
        try:
            try:
                from boxmot import BoTSORT
                self._tracker = BoTSORT(
                    track_high_thresh=self._track_high_thresh,
                    track_low_thresh=self._track_low_thresh,
                    new_track_thresh=self._new_track_thresh,
                    track_buffer=self._track_buffer,
                    match_thresh=self._match_thresh,
                )
                self._uses_fallback = False
                logger.info("BoTSORTAdapter initialized using BoxMOT BoTSORT.")
            except ImportError:
                from ultralytics.trackers.bot_sort import BOTSORT as UltraBoTSORT

                class _Args:
                    track_high_thresh = self._track_high_thresh
                    track_low_thresh = self._track_low_thresh
                    new_track_thresh = self._new_track_thresh
                    track_buffer = self._track_buffer
                    match_thresh = self._match_thresh
                    gmc_method = "sparseOptFlow"
                    proximity_thresh = 0.5
                    appearance_thresh = 0.25
                    with_reid = False

                self._tracker = UltraBoTSORT(args=_Args())
                self._uses_fallback = False
                logger.info("BoTSORTAdapter initialized using Ultralytics BOTSORT engine.")
        except Exception as exc:
            logger.warning(
                "External BoT-SORT library not available (%s). "
                "BoTSORTAdapter operating in robust fallback association mode.",
                exc,
            )
            self._tracker = None
            self._uses_fallback = True

        self._internal_tracks.clear()
        self._next_id = 1
        self._initialized = True
        logger.info(
            "BoTSORTAdapter initialized (track_high=%.2f, buffer=%d, fallback=%s)",
            self._track_high_thresh,
            self._track_buffer,
            self._uses_fallback,
        )

    def track(
        self,
        frame: NDArray[np.uint8],
        detection_result: DetectionResult,
    ) -> TrackingResult:
        """Run BoT-SORT tracking association on incoming frame detections.

        Args:
            frame: Current video frame (BGR uint8 numpy array).
            detection_result: Detections produced by DetectorPort.

        Returns:
            TrackingResult containing list of TrackerResult objects.

        Raises:
            RuntimeError: If track() is called before initialize().
        """
        if not self._initialized:
            raise RuntimeError("BoTSORTAdapter must be initialized via initialize() before track().")

        start = time.perf_counter()
        detections = list(detection_result.detections)

        if self._uses_fallback or self._tracker is None:
            results = self._track_fallback(detections)
        else:
            try:
                results = self._track_external(frame, detections)
            except Exception as exc:
                logger.warning("External BoT-SORT track update failed (%s). Using fallback association.", exc)
                results = self._track_fallback(detections)

        elapsed_ms = (time.perf_counter() - start) * 1000.0

        return TrackingResult(
            results=results,
            tracker_name=self.name,
            inference_time_ms=elapsed_ms,
        )

    def reset(self) -> None:
        """Reset internal tracker state."""
        self._tracker = None
        self._internal_tracks.clear()
        self._next_id = 1
        self._initialized = False
        logger.info("BoTSORTAdapter reset")

    # --- External Tracker Integration ---

    def _track_external(
        self, frame: NDArray[np.uint8], detections: list[Detection]
    ) -> list[TrackerResult]:
        """Execute external BoT-SORT update and convert outputs into TrackerResult instances."""
        if not detections:
            return []

        det_arr = []
        for d in detections:
            det_arr.append([d.bbox.x1, d.bbox.y1, d.bbox.x2, d.bbox.y2, d.confidence, 0])
        dets_np = np.array(det_arr, dtype=np.float32)

        if hasattr(self._tracker, "update"):
            raw_tracks = self._tracker.update(dets_np, frame)
        else:
            raw_tracks = self._tracker.update(dets_np)

        return self._convert_raw_tracks(raw_tracks, detections)

    def _convert_raw_tracks(
        self, raw_tracks: Any, original_detections: list[Detection]
    ) -> list[TrackerResult]:
        """Convert raw tracking outputs into framework TrackerResult instances, preserving PoseKeypoints."""
        results: list[TrackerResult] = []
        if raw_tracks is None or len(raw_tracks) == 0:
            return results

        raw_arr = np.asarray(raw_tracks)
        known_ids = {t.track_id for t in self._internal_tracks}

        for trk in raw_arr:
            if len(trk) >= 5:
                x1, y1, x2, y2 = int(trk[0]), int(trk[1]), int(trk[2]), int(trk[3])
                track_id = int(trk[4])
                conf = float(trk[5]) if len(trk) >= 6 else 0.85

                bbox = BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2)

                best_match = self._find_best_matching_detection(bbox, original_detections)
                keypoints = best_match.keypoints if best_match else None
                det_class = best_match.detection_class if best_match else DetectionClass.PERSON

                matched_detection = Detection(
                    bbox=bbox,
                    confidence=conf,
                    detection_class=det_class,
                    keypoints=keypoints,
                )

                is_new = track_id not in known_ids
                if is_new:
                    logger.debug("Track Created: ID #%d", track_id)
                    self._internal_tracks.append(_InternalTrackState(track_id=track_id, last_detection=matched_detection))
                else:
                    logger.debug("Track Re-associated: ID #%d", track_id)

                results.append(
                    TrackerResult(
                        track_id=track_id,
                        detection=matched_detection,
                        is_new=is_new,
                    )
                )

        return results

    # --- Fallback Association ---

    def _track_fallback(self, detections: list[Detection]) -> list[TrackerResult]:
        """IoU + Nearest-neighbor greedy data association fallback."""
        results: list[TrackerResult] = []
        used_det_indices: set[int] = set()

        for track in self._tracks_active:
            best_idx: Optional[int] = None
            best_dist = self._match_thresh

            track_bbox = track.last_detection.bbox

            for i, det in enumerate(detections):
                if i in used_det_indices:
                    continue

                iou_val = track_bbox.iou(det.bbox)
                if iou_val > (1.0 - best_dist):
                    best_dist = 1.0 - iou_val
                    best_idx = i

            if best_idx is not None:
                used_det_indices.add(best_idx)
                track.last_detection = detections[best_idx]
                track.miss_count = 0

                logger.debug("Track Re-associated (fallback): ID #%d", track.track_id)
                results.append(
                    TrackerResult(
                        track_id=track.track_id,
                        detection=detections[best_idx],
                        is_new=False,
                    )
                )
            else:
                track.miss_count += 1
                logger.debug("Track Lost (missed %d frames): ID #%d", track.miss_count, track.track_id)

        for i, det in enumerate(detections):
            if i in used_det_indices:
                continue

            new_id = self._next_id
            self._next_id += 1

            logger.debug("Track Created (fallback): ID #%d", new_id)
            new_track = _InternalTrackState(
                track_id=new_id,
                last_detection=det,
                miss_count=0,
            )
            self._internal_tracks.append(new_track)

            results.append(
                TrackerResult(
                    track_id=new_id,
                    detection=det,
                    is_new=True,
                )
            )

        # Cleanup lost tracks
        for t in self._internal_tracks:
            if t.miss_count >= self._track_buffer:
                logger.debug("Track Removed: ID #%d", t.track_id)

        self._internal_tracks = [
            t for t in self._internal_tracks if t.miss_count < self._track_buffer
        ]

        return results

    @property
    def _tracks_active(self) -> list[_InternalTrackState]:
        """Active internal track states."""
        return [t for t in self._internal_tracks if t.miss_count < self._track_buffer]

    @staticmethod
    def _find_best_matching_detection(
        bbox: BoundingBox, detections: list[Detection]
    ) -> Optional[Detection]:
        """Find detection with highest IoU to the target bounding box."""
        best_det: Optional[Detection] = None
        best_iou = 0.0

        for det in detections:
            iou_val = bbox.iou(det.bbox)
            if iou_val > best_iou:
                best_iou = iou_val
                best_det = det

        return best_det
