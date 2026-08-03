"""
Event Comparator Module.

Matches annotated Ground Truth events against runtime generated StandardAnalyticsEvents using
configurable spatial, temporal, and track ID tolerances.
Classifies pairs into True Positives (TP), False Positives (FP), and False Negatives (FN).
"""

from __future__ import annotations

import logging
from typing import Any

from camera_analytics.communication.models import StandardAnalyticsEvent
from camera_analytics.validation.schema import (
    EventMatchResult,
    GroundTruthEvent,
    MatchStatus,
    ValidationTolerance,
)

logger = logging.getLogger(__name__)


class EventComparator:
    """Compares expected GroundTruthEvent lists against generated runtime events."""

    def __init__(self, tolerance: ValidationTolerance = ValidationTolerance()) -> None:
        self.tolerance = tolerance

    def compare(
        self,
        ground_truth_events: list[GroundTruthEvent],
        generated_events: list[StandardAnalyticsEvent],
    ) -> list[EventMatchResult]:
        """Match ground truth events against generated runtime events.

        Args:
            ground_truth_events: List of annotated expected events.
            generated_events: List of runtime StandardAnalyticsEvent instances.

        Returns:
            List of EventMatchResult instances (TP, FP, FN).
        """
        results: list[EventMatchResult] = []
        gen_dicts = [e.to_dict(detail_level="full") for e in generated_events]
        matched_gen_indices: set[int] = set()

        # Match each ground truth event to closest matching generated event
        for gt in ground_truth_events:
            best_match_idx: int = -1
            best_frame_diff: int = 999999

            for idx, gen in enumerate(gen_dicts):
                if idx in matched_gen_indices:
                    continue

                # Type check
                if gen.get("event_type") != gt.event_type:
                    continue

                # Zone check if required
                if self.tolerance.match_zone_id and gt.zone_id:
                    if gen.get("zone_id") != gt.zone_id:
                        continue

                # Track ID check if required and available
                if self.tolerance.match_track_id and gt.track_id and gen.get("track_id"):
                    if gen.get("track_id") != gt.track_id:
                        continue

                # Frame & Time tolerance check
                gen_frame = int(gen.get("frame_index", 0))
                frame_diff = abs(gen_frame - gt.frame_index)

                if frame_diff <= self.tolerance.frame_tolerance and frame_diff < best_frame_diff:
                    best_frame_diff = frame_diff
                    best_match_idx = idx

            if best_match_idx != -1:
                matched_gen_indices.add(best_match_idx)
                gen_match = gen_dicts[best_match_idx]
                delay_frames = int(gen_match.get("frame_index", 0)) - gt.frame_index
                gen_ts = float(gen_match.get("metadata", {}).get("frame", {}).get("timestamp", gt.timestamp))
                delay_sec = max(0.0, gen_ts - gt.timestamp)

                results.append(
                    EventMatchResult(
                        status=MatchStatus.TRUE_POSITIVE,
                        ground_truth=gt,
                        generated_event=gen_match,
                        detection_delay_frames=delay_frames,
                        detection_delay_seconds=delay_sec,
                    )
                )
            else:
                # Missed expected event -> False Negative
                results.append(
                    EventMatchResult(
                        status=MatchStatus.FALSE_NEGATIVE,
                        ground_truth=gt,
                        generated_event=None,
                        detection_delay_frames=0,
                        detection_delay_seconds=0.0,
                    )
                )

        # Unmatched generated events -> False Positives
        for idx, gen in enumerate(gen_dicts):
            if idx not in matched_gen_indices:
                results.append(
                    EventMatchResult(
                        status=MatchStatus.FALSE_POSITIVE,
                        ground_truth=None,
                        generated_event=gen,
                        detection_delay_frames=0,
                        detection_delay_seconds=0.0,
                    )
                )

        tp_count = sum(1 for r in results if r.status == MatchStatus.TRUE_POSITIVE)
        fp_count = sum(1 for r in results if r.status == MatchStatus.FALSE_POSITIVE)
        fn_count = sum(1 for r in results if r.status == MatchStatus.FALSE_NEGATIVE)

        logger.info(
            "EventComparator completed comparison: TP=%d, FP=%d, FN=%d (Total matched results=%d)",
            tp_count,
            fp_count,
            fn_count,
            len(results),
        )

        return results
