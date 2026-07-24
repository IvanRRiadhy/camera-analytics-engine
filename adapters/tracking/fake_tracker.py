"""
Fake tracker adapter.

A synthetic implementation of TrackerPort for testing and
development. Assigns persistent track IDs to detections based
on spatial proximity (nearest-neighbor matching), simulating
basic tracking behavior without any real tracking algorithm.

Use this to verify the full pipeline flow (detect -> track ->
process) without loading BoT-SORT or any real tracker.

Example::

    tracker = FakeTracker()
    tracker.initialize()

    # Frame 1: assign new IDs
    result = tracker.track(frame, det_result)
    print(result.track_ids)  # [1, 2, 3]

    # Frame 2: match to existing tracks
    result = tracker.track(frame, det_result)
    print(result.track_ids)  # [1, 2, 3] (same IDs if positions similar)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

import numpy as np

from camera_analytics.core.ports import DetectionResult, TrackerPort, TrackingResult
from camera_analytics.core.track_manager import TrackerResult
from camera_analytics.models.detection import Detection

if TYPE_CHECKING:
    from numpy.typing import NDArray

logger = logging.getLogger(__name__)


@dataclass
class _InternalTrack:
    """Internal track state for nearest-neighbor matching.

    Attributes:
        track_id: Assigned track ID.
        last_detection: Most recent detection for this track.
        miss_count: Consecutive frames without a match.
    """

    track_id: int
    last_detection: Detection
    miss_count: int = 0


class FakeTracker(TrackerPort):
    """Synthetic tracker that assigns persistent IDs via nearest-neighbor.

    Maintains internal track state across frames. For each new frame,
    matches incoming detections to existing tracks by bounding box
    center distance (Hungarian-free — simple greedy matching).

    New detections that don't match any existing track get a new ID.
    Existing tracks that are not matched increment their miss counter
    and are eventually dropped.

    Args:
        max_distance: Maximum pixel distance for matching (default 150).
        max_lost: Frames before a lost track is dropped (default 10).

    Example::

        tracker = FakeTracker(max_distance=200, max_lost=15)
        tracker.initialize()

        result = tracker.track(frame, det_result)
        for r in result.results:
            print(f"Track {r.track_id}: {r.detection.bbox}, new={r.is_new}")
    """

    def __init__(
        self,
        max_distance: float = 150.0,
        max_lost: int = 10,
    ) -> None:
        self._max_distance = max_distance
        self._max_lost = max_lost
        self._tracks: list[_InternalTrack] = []
        self._next_id: int = 1
        self._initialized = False

    @property
    def name(self) -> str:
        """Tracker name."""
        return "fake_tracker"

    def initialize(self, config: Optional[dict[str, object]] = None) -> None:
        """Initialize the tracker.

        Args:
            config: Optional configuration overrides.
        """
        if config:
            self._max_distance = float(
                config.get("max_distance", self._max_distance)
            )
            self._max_lost = int(
                config.get("max_lost", self._max_lost)
            )

        self._tracks = []
        self._next_id = 1
        self._initialized = True

        logger.info(
            "FakeTracker initialized (max_dist=%.0f, max_lost=%d)",
            self._max_distance,
            self._max_lost,
        )

    def track(
        self,
        frame: NDArray[np.uint8],
        detection_result: DetectionResult,
    ) -> TrackingResult:
        """Match detections to existing tracks and assign IDs.

        Uses greedy nearest-neighbor matching by bounding box center
        distance. Unmatched detections create new tracks. Unmatched
        tracks increment their miss counter.

        Args:
            frame: Video frame (not used by fake tracker).
            detection_result: Detections from DetectorPort.

        Returns:
            TrackingResult with track ID assignments.

        Raises:
            RuntimeError: If initialize() has not been called.
        """
        if not self._initialized:
            raise RuntimeError(
                "FakeTracker.initialize() must be called before track()."
            )

        start = time.perf_counter()

        detections = list(detection_result.detections)
        results = self._match_and_assign(detections)

        # Remove stale tracks
        self._cleanup_lost()

        elapsed_ms = (time.perf_counter() - start) * 1000

        return TrackingResult(
            results=results,
            tracker_name=self.name,
            inference_time_ms=elapsed_ms,
        )

    def reset(self) -> None:
        """Reset all tracker state."""
        self._tracks.clear()
        self._next_id = 1
        logger.info("FakeTracker reset")

    # --- Internal Matching ---

    def _match_and_assign(
        self, detections: list[Detection]
    ) -> list[TrackerResult]:
        """Greedy nearest-neighbor matching.

        For each existing track, find the closest unmatched detection.
        If distance < max_distance, it's a match. Remaining unmatched
        detections get new track IDs.

        Args:
            detections: List of detections to match.

        Returns:
            List of TrackerResult with track ID assignments.
        """
        results: list[TrackerResult] = []
        used_detection_indices: set[int] = set()

        # Step 1: Match existing tracks to detections (greedy)
        for track in self._tracks:
            best_idx: int | None = None
            best_dist: float = self._max_distance

            track_center = track.last_detection.bbox.center

            for i, det in enumerate(detections):
                if i in used_detection_indices:
                    continue

                det_center = det.bbox.center
                dist = self._euclidean_distance(track_center, det_center)

                if dist < best_dist:
                    best_dist = dist
                    best_idx = i

            if best_idx is not None:
                # Matched — update track
                used_detection_indices.add(best_idx)
                track.last_detection = detections[best_idx]
                track.miss_count = 0

                results.append(
                    TrackerResult(
                        track_id=track.track_id,
                        detection=detections[best_idx],
                        is_new=False,
                    )
                )
            else:
                # Not matched — increment miss
                track.miss_count += 1

        # Step 2: Create new tracks for unmatched detections
        for i, det in enumerate(detections):
            if i in used_detection_indices:
                continue

            new_track = _InternalTrack(
                track_id=self._next_id,
                last_detection=det,
                miss_count=0,
            )
            self._tracks.append(new_track)

            results.append(
                TrackerResult(
                    track_id=self._next_id,
                    detection=det,
                    is_new=True,
                )
            )

            self._next_id += 1

        return results

    def _cleanup_lost(self) -> None:
        """Remove tracks that have exceeded max_lost frames."""
        before = len(self._tracks)
        self._tracks = [
            t for t in self._tracks if t.miss_count < self._max_lost
        ]
        removed = before - len(self._tracks)
        if removed > 0:
            logger.debug("FakeTracker dropped %d lost tracks", removed)

    @staticmethod
    def _euclidean_distance(
        a: tuple[int, int], b: tuple[int, int]
    ) -> float:
        """Euclidean distance between two (x, y) points."""
        return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5

    @property
    def active_track_count(self) -> int:
        """Number of currently active internal tracks."""
        return len(self._tracks)
