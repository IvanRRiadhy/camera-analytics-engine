"""
Temporal Consensus Engine and Per-Person Cooldown Manager for Face Trajectories.
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class FaceObservation:
    """Single facial recognition observation recorded for a tracked trajectory.

    Attributes:
        person_id: Enrolled person ID if candidate passed initial threshold, else None.
        score: Top-1 similarity score.
        margin: Score delta between top-1 and top-2 person candidates.
        timestamp_s: Frame presentation timestamp in seconds.
        frame_idx: Video frame index.
        metadata: Associated person metadata.
    """

    person_id: Optional[str]
    score: float
    margin: float
    timestamp_s: float
    frame_idx: int
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ConsensusResult:
    """Output of temporal voting evaluation across an observation buffer."""

    person_id: str
    best_score: float
    best_margin: float
    matched_frames: int
    metadata: Dict[str, Any] = field(default_factory=dict)


class ConsensusBuffer:
    """Sliding-window buffer aggregating facial recognition observations along a track."""

    def __init__(self, window_size: int = 15) -> None:
        self.window_size = max(1, int(window_size))
        self.observations: Deque[FaceObservation] = deque(maxlen=self.window_size)

    def add_observation(self, observation: FaceObservation) -> None:
        """Append an observation to the sliding window."""
        self.observations.append(observation)

    def evaluate_consensus(
        self,
        cosine_threshold: float,
        min_margin: float,
        consensus_frames: int,
    ) -> Optional[ConsensusResult]:
        """Evaluate whether sliding window satisfies temporal voting consensus.

        A track is IDENTIFIED when, within the last consensus_window observations,
        at least consensus_frames observations name the same person with
        score >= cosine_threshold and margin >= min_margin.

        Args:
            cosine_threshold: Minimum similarity score required per observation.
            min_margin: Minimum score separation from top-2 candidate required per observation.
            consensus_frames: Minimum required observation count for the candidate person.

        Returns:
            ConsensusResult if consensus criteria are satisfied, otherwise None.
        """
        if not self.observations or consensus_frames <= 0:
            return None

        # Filter observations that strictly satisfy threshold and margin gates
        person_valid_obs: Dict[str, List[FaceObservation]] = {}

        for obs in self.observations:
            if obs.person_id is None:
                continue
            if obs.score >= cosine_threshold and obs.margin >= min_margin:
                person_valid_obs.setdefault(obs.person_id, []).append(obs)

        if not person_valid_obs:
            return None

        # Find the person candidate with the maximum number of valid observations
        best_candidate: Optional[str] = None
        best_count = 0
        for p_id, obs_list in person_valid_obs.items():
            cnt = len(obs_list)
            if cnt > best_count:
                best_count = cnt
                best_candidate = p_id

        if best_candidate is None or best_count < consensus_frames:
            return None

        valid_list = person_valid_obs[best_candidate]
        max_score = max(o.score for o in valid_list)
        max_margin = max(o.margin for o in valid_list)
        last_meta = valid_list[-1].metadata if valid_list else {}

        return ConsensusResult(
            person_id=best_candidate,
            best_score=round(max_score, 4),
            best_margin=round(max_margin, 4),
            matched_frames=best_count,
            metadata=last_meta,
        )


class PersonCooldownManager:
    """Tracks per-person emission timestamps to prevent redundant spamming of events."""

    def __init__(self, cooldown_s: float = 10.0) -> None:
        self.cooldown_s = float(cooldown_s)
        self._last_emission: Dict[str, float] = {}

    def is_cooled_down(self, person_id: str, current_time_s: float) -> bool:
        """Check whether sufficient time has elapsed since the last emission for person_id."""
        last_time = self._last_emission.get(person_id)
        if last_time is None:
            return True
        return (current_time_s - last_time) >= self.cooldown_s

    def record_emission(self, person_id: str, current_time_s: float) -> None:
        """Record an emission event timestamp for person_id."""
        self._last_emission[person_id] = current_time_s

