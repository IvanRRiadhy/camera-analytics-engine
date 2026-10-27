"""
Attribute Stabilization Layer Implementation (Sprint H1.4.7).

Provides model-agnostic temporal stabilization across consecutive tracked frames:
- Exponential Moving Average (EMA) for continuous scalar attributes (e.g. age).
- Majority Voting Window for categorical attributes (e.g. gender, emotion, ppe).
- Confidence Locking via AttributeLockManager.
- Confidence Decay over missing or occluded frames.
"""

from __future__ import annotations

import logging
import time
from collections import Counter, deque
from dataclasses import dataclass, field
from typing import Any, Optional

from camera_analytics.core.human.decoder import HumanAttributes, InferenceResult
from camera_analytics.core.human.lock_manager import AttributeLockManager, AttributeLockState
from camera_analytics.core.human.models import DemographicsState, ExpressionState, HumanState, PPEState

logger = logging.getLogger(__name__)


@dataclass
class TrackStabilizationHistory:
    """Historical buffer of recent raw predictions for a single track ID."""

    track_id: int
    ema_age: Optional[float] = None
    gender_window: deque[tuple[str, float]] = field(default_factory=lambda: deque(maxlen=15))
    emotion_window: deque[tuple[str, float]] = field(default_factory=lambda: deque(maxlen=15))
    last_update_timestamp: float = field(default_factory=time.time)
    consecutive_missing_frames: int = 0


class AttributeStabilizer:
    """Generic temporal stabilizer operating on InferenceResult objects before state mutation."""

    def __init__(
        self,
        ema_alpha: float = 0.20,
        majority_window_size: int = 15,
        lock_threshold: float = 0.80,
        confidence_decay_rate: float = 0.05,
    ) -> None:
        self.ema_alpha = ema_alpha
        self.majority_window_size = majority_window_size
        self.lock_threshold = lock_threshold
        self.confidence_decay_rate = confidence_decay_rate
        self.lock_manager = AttributeLockManager()
        self._histories: dict[int, TrackStabilizationHistory] = {}

    def get_history(self, track_id: int) -> TrackStabilizationHistory:
        """Retrieve or instantiate stabilization history buffer for a track."""
        if track_id not in self._histories:
            self._histories[track_id] = TrackStabilizationHistory(
                track_id=track_id,
                gender_window=deque(maxlen=self.majority_window_size),
                emotion_window=deque(maxlen=self.majority_window_size),
            )
        return self._histories[track_id]

    def stabilize(self, result: InferenceResult, current_state: HumanState) -> HumanAttributes:
        """Stabilize raw InferenceResult attributes using temporal smoothing algorithms.

        Args:
            result: Decoupled inference result DTO.
            current_state: Current domain HumanState.

        Returns:
            Stabilized HumanAttributes container.
        """
        hist = self.get_history(result.track_id)
        raw_attrs = result.attributes
        stabilized = HumanAttributes()

        # 1. EMA Age Stabilization
        if raw_attrs.age is not None:
            if hist.ema_age is None:
                hist.ema_age = float(raw_attrs.age)
            else:
                hist.ema_age = (self.ema_alpha * float(raw_attrs.age)) + ((1.0 - self.ema_alpha) * hist.ema_age)
            stabilized.age = round(hist.ema_age, 1)

        # 2. Majority Voting Gender Stabilization
        if raw_attrs.gender is not None:
            hist.gender_window.append((raw_attrs.gender, raw_attrs.confidence))
            # Vote on most frequent prediction in history window
            g_counts = Counter(g for g, c in hist.gender_window)
            top_gender, top_count = g_counts.most_common(1)[0]
            top_confs = [c for g, c in hist.gender_window if g == top_gender]
            avg_g_conf = float(sum(top_confs) / len(top_confs)) if top_confs else raw_attrs.confidence

            # Check attribute lock
            if avg_g_conf >= self.lock_threshold:
                stabilized.gender = top_gender
                current_state.demographics.gender_lock = AttributeLockState.LOCKED.value
            elif current_state.demographics.gender_lock == AttributeLockState.LOCKED.value:
                stabilized.gender = current_state.demographics.gender or top_gender
            else:
                stabilized.gender = top_gender

        # 3. Majority Voting Emotion Stabilization
        if raw_attrs.emotion is not None:
            hist.emotion_window.append((raw_attrs.emotion, raw_attrs.confidence))
            e_counts = Counter(e for e, c in hist.emotion_window)
            top_emotion, _ = e_counts.most_common(1)[0]
            stabilized.emotion = top_emotion

        # 4. Identity & PPE Pass-through
        if raw_attrs.identity_id is not None:
            stabilized.identity_id = raw_attrs.identity_id
        if raw_attrs.ppe_helmet is not None:
            stabilized.ppe_helmet = raw_attrs.ppe_helmet

        stabilized.confidence = result.confidence
        hist.last_update_timestamp = time.time()
        hist.consecutive_missing_frames = 0

        return stabilized

    def apply_decay(self, track_id: int, state: HumanState) -> None:
        """Apply confidence decay when predictions are skipped or occluded."""
        hist = self._histories.get(track_id)
        if hist:
            hist.consecutive_missing_frames += 1
            decay_factor = max(0.0, 1.0 - (hist.consecutive_missing_frames * self.confidence_decay_rate))
            if state.demographics.gender_confidence:
                state.demographics.gender_confidence = round(state.demographics.gender_confidence * decay_factor, 3)

    def purge_track(self, track_id: int) -> None:
        """Purge track stabilization history upon track termination."""
        self._histories.pop(track_id, None)
