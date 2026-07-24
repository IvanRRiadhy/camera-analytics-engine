"""
Track manager.

Centralized manager for the lifecycle of all Track objects.
TrackManager owns every track — it creates, updates, confirms,
marks lost, and removes tracks. BoT-SORT (or any tracker) sends
its results here; TrackManager maintains the persistent state.

Design decisions:
    - Track mutation methods live HERE, not on Track itself.
      Track is a data object; TrackManager is the behavior owner.
    - Track history uses a bounded deque to prevent memory leaks.
    - All tracks (active + archived) are accessible for analytics.
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
from typing import Optional

from camera_analytics.core.track_features import TrackFeatureStore
from camera_analytics.models.detection import BoundingBox, Detection
from camera_analytics.models.track import Track, TrackSnapshot, TrackState

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TrackerResult:
    """Output from a tracker (e.g., BoT-SORT) for one tracked object.

    This is the interface between the tracker and TrackManager.
    The tracker provides the association (track_id ↔ detection),
    and TrackManager handles the rest.

    Attributes:
        track_id: Tracker-assigned ID.
        detection: The detection associated with this track.
        is_new: Whether this is a newly created track.
    """

    track_id: int
    detection: Detection
    is_new: bool = False


class TrackManager:
    """Centralized track lifecycle manager.

    Owns all Track objects. Receives tracker output and maintains
    persistent track state across frames. Provides lookup methods
    for analytics modules.

    Track lifecycle::

        TENTATIVE ──(confirm_after_n hits)──> CONFIRMED
        CONFIRMED ──(miss_count > threshold)──> LOST
        LOST ──────(re-detected)──────────────> CONFIRMED
        LOST ──────(max_lost_age exceeded)────> DELETED (archived)

    Args:
        max_history_length: Max snapshots per track (rolling window).
        confirm_after_n: Number of hits before TENTATIVE → CONFIRMED.
        max_lost_age: Frames without detection before LOST → DELETED.

    Example::

        manager = TrackManager(max_history_length=150, max_lost_age=30)

        # Each frame: receive tracker output, update state
        manager.update_from_tracker(tracker_results, frame_index=42)

        # Query
        confirmed = manager.get_confirmed()
        person_in_lobby = manager.get_in_zone(lobby_zone)
    """

    def __init__(
        self,
        max_history_length: int = 150,
        confirm_after_n: int = 3,
        max_lost_age: int = 30,
    ) -> None:
        self._active_tracks: dict[int, Track] = {}
        self._archived_tracks: dict[int, Track] = {}
        self._max_history_length = max_history_length
        self._confirm_after_n = confirm_after_n
        self._max_lost_age = max_lost_age
        self._total_created: int = 0
        self._total_deleted: int = 0

    # --- Core Update ---

    def update_from_tracker(
        self,
        results: list[TrackerResult],
        frame_index: int,
    ) -> None:
        """Process tracker output for one frame.

        Creates new tracks, updates existing ones, and marks
        unmatched tracks as missed. Then runs lifecycle transitions
        (confirm tentative, delete stale lost).

        Args:
            results: Tracker output — list of (track_id, detection) pairs.
            frame_index: Current frame index.
        """
        matched_ids: set[int] = set()

        for result in results:
            matched_ids.add(result.track_id)

            if result.track_id in self._active_tracks:
                # Update existing track
                self._update_track(
                    result.track_id, result.detection, frame_index
                )
            else:
                # Create new track
                self._create_track(
                    result.track_id, result.detection, frame_index
                )

        # Mark unmatched active tracks as missed
        for track_id in list(self._active_tracks.keys()):
            if track_id not in matched_ids:
                self._mark_missed(track_id)

        # Run lifecycle transitions
        self._run_lifecycle(frame_index)

    # --- Track Mutations (internal) ---

    def _create_track(
        self,
        track_id: int,
        detection: Detection,
        frame_index: int,
    ) -> Track:
        """Create a new track."""
        track = Track(
            track_id=track_id,
            detection=detection,
            state=TrackState.TENTATIVE,
            history=[],
            first_frame=frame_index,
            last_frame=frame_index,
            hit_count=1,
            miss_count=0,
        )

        # Replace list with bounded deque
        track.history = deque(maxlen=self._max_history_length)

        # Add initial snapshot
        snapshot = TrackSnapshot(
            frame_index=frame_index,
            bbox=detection.bbox,
            detection=detection,
        )
        track.history.append(snapshot)

        # Initialize feature store
        track.features = TrackFeatureStore()

        self._active_tracks[track_id] = track
        self._total_created += 1

        logger.debug("Track %d created at frame %d", track_id, frame_index)
        return track

    def _update_track(
        self,
        track_id: int,
        detection: Detection,
        frame_index: int,
    ) -> None:
        """Update an existing track with a new detection."""
        track = self._active_tracks[track_id]

        # Record snapshot (deque auto-evicts oldest if full)
        snapshot = TrackSnapshot(
            frame_index=frame_index,
            bbox=detection.bbox,
            detection=detection,
        )
        track.history.append(snapshot)

        # Update current state
        track.detection = detection
        track.last_frame = frame_index
        track.hit_count += 1
        track.miss_count = 0

        # Re-confirm if was lost
        if track.state == TrackState.LOST:
            track.state = TrackState.CONFIRMED
            logger.debug("Track %d re-confirmed at frame %d", track_id, frame_index)

    def _mark_missed(self, track_id: int) -> None:
        """Increment miss counter for an unmatched track."""
        track = self._active_tracks.get(track_id)
        if track is not None:
            track.miss_count += 1

    def _run_lifecycle(self, frame_index: int) -> None:
        """Run lifecycle state transitions.

        - TENTATIVE → CONFIRMED (after enough hits)
        - CONFIRMED → LOST (after missing threshold)
        - LOST → DELETED (after max lost age)
        """
        to_delete: list[int] = []

        for track_id, track in self._active_tracks.items():
            # TENTATIVE → CONFIRMED
            if (
                track.state == TrackState.TENTATIVE
                and track.hit_count >= self._confirm_after_n
            ):
                track.state = TrackState.CONFIRMED

            # CONFIRMED → LOST
            elif (
                track.state == TrackState.CONFIRMED
                and track.miss_count > 0
            ):
                track.state = TrackState.LOST

            # LOST → DELETED
            if (
                track.state == TrackState.LOST
                and track.miss_count >= self._max_lost_age
            ):
                track.state = TrackState.DELETED
                to_delete.append(track_id)

        # Archive deleted tracks
        for track_id in to_delete:
            track = self._active_tracks.pop(track_id)
            self._archived_tracks[track_id] = track
            self._total_deleted += 1
            logger.debug("Track %d archived at frame %d", track_id, frame_index)

    # --- Query: Active Tracks ---

    def get_active(self) -> list[Track]:
        """Get all active tracks (not deleted/archived).

        Returns:
            List of active Track objects.
        """
        return list(self._active_tracks.values())

    def get_confirmed(self) -> list[Track]:
        """Get only confirmed tracks.

        Returns:
            List of tracks in CONFIRMED state.
        """
        return [
            t
            for t in self._active_tracks.values()
            if t.state == TrackState.CONFIRMED
        ]

    def get_tentative(self) -> list[Track]:
        """Get tentative (unconfirmed) tracks.

        Returns:
            List of tracks in TENTATIVE state.
        """
        return [
            t
            for t in self._active_tracks.values()
            if t.state == TrackState.TENTATIVE
        ]

    def get_lost(self) -> list[Track]:
        """Get lost tracks (still active, not yet archived).

        Returns:
            List of tracks in LOST state.
        """
        return [
            t
            for t in self._active_tracks.values()
            if t.state == TrackState.LOST
        ]

    def get_by_id(self, track_id: int) -> Optional[Track]:
        """Look up a track by its ID (active or archived).

        Args:
            track_id: The track ID to search for.

        Returns:
            The Track, or None if not found.
        """
        track = self._active_tracks.get(track_id)
        if track is None:
            track = self._archived_tracks.get(track_id)
        return track

    def get_by_global_id(self, global_id: int) -> list[Track]:
        """Find all tracks assigned to a global ReID identity.

        Searches both active and archived tracks.

        Args:
            global_id: The global person ID to search for.

        Returns:
            List of tracks with matching global_id.
        """
        result: list[Track] = []
        for track in self._active_tracks.values():
            if track.global_id == global_id:
                result.append(track)
        for track in self._archived_tracks.values():
            if track.global_id == global_id:
                result.append(track)
        return result

    def get_by_state(self, state: TrackState) -> list[Track]:
        """Get active tracks filtered by state.

        Args:
            state: The TrackState to filter by.

        Returns:
            List of matching tracks.
        """
        return [
            t
            for t in self._active_tracks.values()
            if t.state == state
        ]

    # --- Track Feature Access ---

    def assign_global_id(self, track_id: int, global_id: int) -> bool:
        """Assign a global ReID identity to a track.

        Args:
            track_id: The track to assign.
            global_id: The global person ID.

        Returns:
            True if the track was found and updated.
        """
        track = self._active_tracks.get(track_id)
        if track is not None:
            track.global_id = global_id
            return True
        return False

    def clear_features_namespace(self, namespace: str) -> int:
        """Clear a feature namespace from all active tracks.

        Called when an analytics module is unregistered.

        Args:
            namespace: The namespace to clear.

        Returns:
            Total number of features removed across all tracks.
        """
        total = 0
        for track in self._active_tracks.values():
            if hasattr(track, "features") and track.features is not None:
                total += track.features.clear_namespace(namespace)
        return total

    # --- Statistics ---

    @property
    def active_count(self) -> int:
        """Number of active tracks."""
        return len(self._active_tracks)

    @property
    def confirmed_count(self) -> int:
        """Number of confirmed tracks."""
        return sum(
            1
            for t in self._active_tracks.values()
            if t.state == TrackState.CONFIRMED
        )

    @property
    def archived_count(self) -> int:
        """Number of archived (deleted) tracks."""
        return len(self._archived_tracks)

    @property
    def total_created(self) -> int:
        """Total tracks ever created."""
        return self._total_created

    @property
    def total_deleted(self) -> int:
        """Total tracks ever deleted/archived."""
        return self._total_deleted

    # --- Maintenance ---

    def prune_archive(self, max_archived: int = 1000) -> int:
        """Remove oldest archived tracks if archive exceeds limit.

        Prevents memory growth from archived tracks on 24/7 deployments.

        Args:
            max_archived: Maximum archived tracks to keep.

        Returns:
            Number of archived tracks removed.
        """
        if len(self._archived_tracks) <= max_archived:
            return 0

        # Sort by last_frame, remove oldest
        sorted_ids = sorted(
            self._archived_tracks.keys(),
            key=lambda tid: self._archived_tracks[tid].last_frame,
        )

        to_remove = len(self._archived_tracks) - max_archived
        removed = 0
        for tid in sorted_ids[:to_remove]:
            del self._archived_tracks[tid]
            removed += 1

        if removed > 0:
            logger.debug("Pruned %d archived tracks", removed)

        return removed

    def clear(self) -> None:
        """Remove all tracks (active and archived)."""
        self._active_tracks.clear()
        self._archived_tracks.clear()

    def __repr__(self) -> str:
        return (
            f"TrackManager("
            f"active={self.active_count}, "
            f"confirmed={self.confirmed_count}, "
            f"archived={self.archived_count}, "
            f"total_created={self._total_created})"
        )
