"""
Detection set.

A lightweight collection wrapper around a list of Detection objects,
providing a fluent filtering API. Prevents every analytics module
from writing its own filtering logic.

All filtering methods return a new DetectionSet (immutable chain),
so the original set is never modified.
"""

from __future__ import annotations

from typing import Iterator, Optional, Sequence

from camera_analytics.models.detection import Detection, DetectionClass
from camera_analytics.models.zone import Zone


class DetectionSet:
    """Filterable collection of Detection objects.

    Wraps a list of detections and provides chainable filtering
    methods. Each filter returns a new DetectionSet, leaving the
    original unchanged.

    Example::

        detections = DetectionSet(raw_detections)

        # Chain filters
        people = detections.persons().above_confidence(0.6)

        # Use in zone check
        in_lobby = detections.persons().in_zone(lobby_zone)

        # Iterate
        for det in people:
            print(det.bbox.center)
    """

    __slots__ = ("_items",)

    def __init__(self, items: Sequence[Detection] = ()) -> None:
        self._items: tuple[Detection, ...] = tuple(items)

    # --- Filtering ---

    def by_class(self, detection_class: DetectionClass) -> DetectionSet:
        """Filter detections to a specific class.

        Args:
            detection_class: The class to keep.

        Returns:
            New DetectionSet containing only matching detections.
        """
        return DetectionSet(
            d for d in self._items if d.detection_class == detection_class
        )

    def persons(self) -> DetectionSet:
        """Filter to person detections only.

        Returns:
            New DetectionSet with only PERSON class detections.
        """
        return self.by_class(DetectionClass.PERSON)

    def above_confidence(self, threshold: float) -> DetectionSet:
        """Filter to detections above a confidence threshold.

        Args:
            threshold: Minimum confidence (inclusive).

        Returns:
            New DetectionSet with detections >= threshold.
        """
        return DetectionSet(
            d for d in self._items if d.confidence >= threshold
        )

    def with_pose(self) -> DetectionSet:
        """Filter to detections that include pose keypoints.

        Returns:
            New DetectionSet with only pose-bearing detections.
        """
        return DetectionSet(d for d in self._items if d.has_pose)

    def in_zone(self, zone: Zone) -> DetectionSet:
        """Filter to detections whose bbox center falls within a zone.

        Args:
            zone: The zone to test against.

        Returns:
            New DetectionSet with detections inside the zone.
        """
        return DetectionSet(
            d for d in self._items if zone.contains_bbox(d.bbox)
        )

    def above_area(self, min_area: int) -> DetectionSet:
        """Filter to detections with bbox area >= min_area.

        Args:
            min_area: Minimum bounding box area in square pixels.

        Returns:
            New DetectionSet with detections meeting the area threshold.
        """
        return DetectionSet(
            d for d in self._items if d.bbox.area >= min_area
        )

    def exclude_class(self, detection_class: DetectionClass) -> DetectionSet:
        """Filter out detections of a specific class.

        Args:
            detection_class: The class to exclude.

        Returns:
            New DetectionSet without the excluded class.
        """
        return DetectionSet(
            d for d in self._items if d.detection_class != detection_class
        )

    # --- Accessors ---

    @property
    def items(self) -> tuple[Detection, ...]:
        """The underlying detection tuple (read-only)."""
        return self._items

    @property
    def count(self) -> int:
        """Number of detections in this set."""
        return len(self._items)

    @property
    def is_empty(self) -> bool:
        """Whether this set contains no detections."""
        return len(self._items) == 0

    def first(self) -> Optional[Detection]:
        """Return the first detection, or None if empty."""
        if self._items:
            return self._items[0]
        return None

    def highest_confidence(self) -> Optional[Detection]:
        """Return the detection with the highest confidence.

        Returns:
            Detection with max confidence, or None if empty.
        """
        if not self._items:
            return None
        return max(self._items, key=lambda d: d.confidence)

    # --- Dunder Methods ---

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self) -> Iterator[Detection]:
        return iter(self._items)

    def __getitem__(self, index: int) -> Detection:
        return self._items[index]

    def __bool__(self) -> bool:
        return len(self._items) > 0

    def __contains__(self, item: Detection) -> bool:
        return item in self._items

    def __add__(self, other: DetectionSet) -> DetectionSet:
        """Combine two DetectionSets."""
        return DetectionSet(self._items + other._items)

    def __repr__(self) -> str:
        return f"DetectionSet(count={len(self._items)})"
