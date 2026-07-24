"""
Track data models.

Represents a tracked object across multiple frames. Track is a
data object — it holds state but does not manage its own lifecycle.
All mutations (create, update, confirm, mark_lost, delete) are
performed by TrackManager.

Sprint 2 changes:
    - Removed mutation methods (update, confirm, mark_lost, delete,
      assign_global_id, set_metadata, get_metadata). These now live
      in TrackManager.
    - Replaced ``metadata: dict`` with ``features: TrackFeatureStore``
      for namespaced, typed per-track data.
    - History type annotation supports both list and deque (TrackManager
      creates tracks with bounded deque).
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Optional, Sequence, Union

from camera_analytics.models.detection import BoundingBox, Detection

if TYPE_CHECKING:
    from camera_analytics.core.track_features import TrackFeatureStore


class TrackState(Enum):
    """Lifecycle state of a track.

    Attributes:
        TENTATIVE: Newly created, not yet confirmed by enough observations.
        CONFIRMED: Actively tracked with consistent observations.
        LOST: Temporarily lost — not detected in recent frames.
        DELETED: Permanently removed from active tracking.
    """

    TENTATIVE = auto()
    CONFIRMED = auto()
    LOST = auto()
    DELETED = auto()


@dataclass(frozen=True, slots=True)
class TrackSnapshot:
    """An immutable snapshot of a track at a specific frame.

    Captures the track's position and detection at one point in time.
    Used to build movement history without mutating the Track itself.

    Attributes:
        frame_index: The frame number when this snapshot was captured.
        bbox: Bounding box position at this frame.
        detection: The full detection that produced this snapshot.
    """

    frame_index: int
    bbox: BoundingBox
    detection: Detection


@dataclass(slots=True)
class Track:
    """A tracked object across multiple video frames.

    Data object that holds track state. All lifecycle mutations
    (create, update, confirm, mark_lost, delete) are performed
    by TrackManager — not by Track itself.

    Attributes:
        track_id: Unique identifier assigned by the tracker (e.g. BoT-SORT).
        detection: The most recent detection for this track.
        state: Current lifecycle state of the track.
        global_id: Optional globally re-identified person ID (from ReID).
        features: Namespaced feature store for per-module data.
        history: Bounded sequence of snapshots (deque with max length).
        first_frame: Frame index when this track was first observed.
        last_frame: Frame index when this track was last observed.
        hit_count: Total number of frames where this track was detected.
        miss_count: Consecutive frames where this track was not detected.
    """

    track_id: int
    detection: Detection
    state: TrackState = TrackState.TENTATIVE
    global_id: Optional[int] = None
    features: Optional[TrackFeatureStore] = field(default=None, repr=False)
    history: Union[deque[TrackSnapshot], list[TrackSnapshot]] = field(
        default_factory=list
    )
    first_frame: int = 0
    last_frame: int = 0
    hit_count: int = 0
    miss_count: int = 0

    # --- Derived Properties (read-only) ---

    @property
    def bbox(self) -> BoundingBox:
        """Current bounding box (shortcut to detection.bbox)."""
        return self.detection.bbox

    @property
    def age(self) -> int:
        """Total frame span from first to last observation."""
        return self.last_frame - self.first_frame

    @property
    def is_confirmed(self) -> bool:
        """Whether this track is in CONFIRMED state."""
        return self.state == TrackState.CONFIRMED

    @property
    def is_lost(self) -> bool:
        """Whether this track is in LOST state."""
        return self.state == TrackState.LOST

    @property
    def is_deleted(self) -> bool:
        """Whether this track is in DELETED state."""
        return self.state == TrackState.DELETED

    @property
    def display_id(self) -> int:
        """The ID to display: global_id if assigned, otherwise track_id."""
        return self.global_id if self.global_id is not None else self.track_id

    @property
    def trajectory(self) -> list[tuple[int, int]]:
        """List of center-point positions from the movement history.

        Returns:
            List of (cx, cy) tuples in chronological order.
        """
        return [snapshot.bbox.center for snapshot in self.history]

    @property
    def history_length(self) -> int:
        """Number of snapshots in the movement history."""
        return len(self.history)

    @property
    def has_features(self) -> bool:
        """Whether this track has an initialized feature store."""
        return self.features is not None

    def __repr__(self) -> str:
        return (
            f"Track(id={self.track_id}, state={self.state.name}, "
            f"global_id={self.global_id}, hits={self.hit_count}, "
            f"misses={self.miss_count}, history={self.history_length})"
        )
