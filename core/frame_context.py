"""
Frame context.

Immutable per-frame data container that carries all information
an analytics module needs to process a single video frame.

FrameContext is created fresh by the Pipeline each frame and passed
to every registered module. It is a pure data object with no side
effects — modules read from it but never mutate it.

Design decisions:
    - No reference to RuntimeState (prevents modules from mutating
      global state through the context).
    - Frozen dataclass (immutable after creation).
    - Pre-computed filtered track lists (cached, not recomputed
      per module).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

import numpy as np

from camera_analytics.core.detection_set import DetectionSet
from camera_analytics.models.camera import Camera
from camera_analytics.models.track import Track
from camera_analytics.models.zone import Zone

if TYPE_CHECKING:
    from numpy.typing import NDArray


@dataclass(frozen=True, slots=True)
class FrameContext:
    """Immutable per-frame data snapshot for analytics modules.

    Created by the Pipeline each frame. Every registered module
    receives the same FrameContext instance. Because it is frozen,
    modules cannot accidentally corrupt shared state.

    Attributes:
        frame_id: Sequential frame counter (1-indexed).
        timestamp: Frame timestamp in seconds from pipeline start.
        image: The video frame as a BGR numpy array (HxWx3, uint8).
        camera_id: ID of the camera that produced this frame.
        detections: DetectionSet with filtering API.
        tracks: Currently active tracked objects (read-only snapshot).
        zones: Dictionary of zones keyed by zone_id.
        frame_width: Frame width in pixels.
        frame_height: Frame height in pixels.
    """

    frame_id: int
    timestamp: float
    image: NDArray[np.uint8]
    camera_id: str
    detections: DetectionSet
    tracks: tuple[Track, ...]
    zones: dict[str, Zone]
    frame_width: int
    frame_height: int

    # --- Pre-computed Cached Views ---
    # These are computed once by the Pipeline when creating the context,
    # so that multiple modules don't recompute the same filters.

    _person_tracks: tuple[Track, ...] = field(
        default=(), repr=False, hash=False, compare=False
    )

    # --- Track Queries ---

    @property
    def person_tracks(self) -> tuple[Track, ...]:
        """Pre-computed list of confirmed person tracks.

        Cached at FrameContext creation time — free for all modules.
        """
        return self._person_tracks

    @property
    def person_count(self) -> int:
        """Number of confirmed person tracks."""
        return len(self._person_tracks)

    @property
    def track_count(self) -> int:
        """Total number of active tracks."""
        return len(self.tracks)

    def get_track_by_id(self, track_id: int) -> Optional[Track]:
        """Find a track by its track_id.

        Args:
            track_id: The tracker-assigned ID to search for.

        Returns:
            The matching Track, or None.
        """
        for track in self.tracks:
            if track.track_id == track_id:
                return track
        return None

    def get_tracks_in_zone(self, zone_id: str) -> tuple[Track, ...]:
        """Get tracks whose bbox center falls within a zone.

        Args:
            zone_id: The zone to test against.

        Returns:
            Tuple of tracks inside the zone.
        """
        zone = self.zones.get(zone_id)
        if zone is None:
            return ()

        return tuple(
            t for t in self.tracks if zone.contains_bbox(t.bbox)
        )

    def get_tracks_by_state(self, state: "TrackState") -> tuple[Track, ...]:
        """Get tracks filtered by lifecycle state.

        Args:
            state: The TrackState to filter by.

        Returns:
            Tuple of tracks in the specified state.
        """
        return tuple(t for t in self.tracks if t.state == state)

    # --- Zone Queries ---

    def get_zone(self, zone_id: str) -> Optional[Zone]:
        """Look up a zone by ID.

        Args:
            zone_id: The zone ID to find.

        Returns:
            The Zone, or None if not found.
        """
        return self.zones.get(zone_id)

    @property
    def zone_names(self) -> list[str]:
        """List of all zone names."""
        return [z.name for z in self.zones.values()]


# --- Import at bottom to avoid circular dependency ---
from camera_analytics.models.track import TrackState  # noqa: E402


def build_frame_context(
    frame_id: int,
    timestamp: float,
    image: NDArray[np.uint8],
    camera_id: str,
    detections: DetectionSet,
    tracks: list[Track],
    zones: dict[str, Zone],
) -> FrameContext:
    """Factory function to build a FrameContext with pre-computed caches.

    Called by the Pipeline each frame. Pre-computes filtered track
    lists so that individual modules don't redundantly filter.

    Args:
        frame_id: Sequential frame counter.
        timestamp: Elapsed time from pipeline start in seconds.
        image: Current video frame (BGR numpy array).
        camera_id: Source camera ID.
        detections: DetectionSet for this frame.
        tracks: Currently active Track objects.
        zones: Dictionary of zones.

    Returns:
        A fully constructed, frozen FrameContext.
    """
    tracks_tuple = tuple(tracks)
    height, width = image.shape[:2]

    # Pre-compute person tracks (confirmed + PERSON class)
    person_tracks = tuple(
        t
        for t in tracks_tuple
        if t.detection.is_person and t.state == TrackState.CONFIRMED
    )

    return FrameContext(
        frame_id=frame_id,
        timestamp=timestamp,
        image=image,
        camera_id=camera_id,
        detections=detections,
        tracks=tracks_tuple,
        zones=zones,
        frame_width=width,
        frame_height=height,
        _person_tracks=person_tracks,
    )
