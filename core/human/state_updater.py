"""
Result Splitter & Human State Updater (Sprint H1.5C).

Splits batched ModuleResult outputs and applies them cleanly to individual track HumanState objects.
Serves as the single owner permitted to mutate HumanState domain entities.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional, Sequence

from camera_analytics.core.human.context import ModuleResult
from camera_analytics.core.human.decoder import InferenceResult
from camera_analytics.core.human.lock_manager import AttributeLockManager
from camera_analytics.core.human.models import CapabilityId, HumanState, HumanStateLifecycle
from camera_analytics.core.human.stabilizer import AttributeStabilizer
from camera_analytics.core.human.timeline import HumanTimelineEntry

logger = logging.getLogger(__name__)


class ResultSplitter:
    """Splits batched ModuleResult objects into per-track result maps."""

    @staticmethod
    def split(results: list[ModuleResult]) -> dict[int, list[ModuleResult]]:
        """Group a list of ModuleResult outputs by track_id."""
        by_track: dict[int, list[ModuleResult]] = {}
        for res in results:
            t_id = res.track_id
            if t_id not in by_track:
                by_track[t_id] = []
            by_track[t_id].append(res)
        return by_track


class HumanStateUpdater:
    """Applies ModuleResult & InferenceResult objects to HumanState domain models as sole mutator."""

    def __init__(self, stabilizer: Optional[AttributeStabilizer] = None) -> None:
        self.splitter = ResultSplitter()
        self.stabilizer = stabilizer or AttributeStabilizer()

    def update_state(self, state: HumanState, results: list[Any]) -> HumanState:
        """Enrich a HumanState object with a sequence of ModuleResult or InferenceResult outputs."""
        state.last_seen_utc = time.time()

        # Update state machine lifecycle
        if state.lifecycle == HumanStateLifecycle.NEW:
            state.lifecycle = HumanStateLifecycle.INITIALIZING
        elif state.lifecycle == HumanStateLifecycle.INITIALIZING and state.statistics.inference_count >= 1:
            state.lifecycle = HumanStateLifecycle.LEARNING
        elif state.lifecycle == HumanStateLifecycle.LEARNING and state.statistics.inference_count >= 5:
            state.lifecycle = HumanStateLifecycle.STABLE

        for res in results:
            if getattr(res, "track_id", None) != state.track_id:
                continue

            # Process InferenceResult DTO
            if isinstance(res, InferenceResult):
                self._apply_inference_result(state, res)
            # Process legacy ModuleResult
            elif isinstance(res, ModuleResult):
                self._apply_module_result(state, res)

        return state

    def _apply_inference_result(self, state: HumanState, res: InferenceResult) -> None:
        """Apply model-agnostic InferenceResult to persistent HumanState."""
        # Stabilize attributes via AttributeStabilizer
        stabilized = self.stabilizer.stabilize(res, state)

        # 1. Update Age CapabilityState & Demographics
        if stabilized.age is not None:
            age_cap = state.get_capability_state(CapabilityId.AGE)
            age_cap.current_value = stabilized.age
            age_cap.confidence = res.confidence
            age_cap.last_seen_utc = time.time()
            age_cap.history.append(stabilized.age, res.confidence)
            age_cap.stabilization.ema_value = stabilized.age
            state.demographics.age = stabilized.age
            state.demographics.age_confidence = res.confidence

            # Append to timeline ring buffer
            state.timeline.append(
                HumanTimelineEntry(
                    timestamp_utc=time.time(),
                    frame_index=0,
                    capability_id=CapabilityId.AGE.value,
                    value=stabilized.age,
                    confidence=res.confidence,
                    latency_ms=res.execution_time_ms,
                    module_id=res.module_id,
                )
            )

        # 2. Update Gender CapabilityState & Demographics
        if stabilized.gender is not None:
            g_cap = state.get_capability_state(CapabilityId.GENDER)
            g_cap.current_value = stabilized.gender
            g_cap.confidence = res.confidence
            g_cap.last_seen_utc = time.time()
            g_cap.history.append(stabilized.gender, res.confidence)
            state.demographics.gender = stabilized.gender
            state.demographics.gender_confidence = res.confidence

            state.timeline.append(
                HumanTimelineEntry(
                    timestamp_utc=time.time(),
                    frame_index=0,
                    capability_id=CapabilityId.GENDER.value,
                    value=stabilized.gender,
                    confidence=res.confidence,
                    latency_ms=res.execution_time_ms,
                    module_id=res.module_id,
                )
            )

        # 3. Record statistics
        state.statistics.record_inference(latency_ms=res.execution_time_ms, quality_score=1.0, success=True)

    def _apply_module_result(self, state: HumanState, res: ModuleResult) -> None:
        """Apply legacy ModuleResult outputs to HumanState."""
        import threading
        bef_demo = f"age={state.demographics.age}, gender={state.demographics.gender}"
        bef_caps = f"age_cap={state.get_capability_state(CapabilityId.AGE).current_value}, g_cap={state.get_capability_state(CapabilityId.GENDER).current_value}"

        state.custom_attributes[res.module_id] = {
            "outputs": res.outputs,
            "confidence": res.confidence,
            "execution_time_ms": res.execution_time_ms,
            "status": res.status,
        }

        if "age" in res.outputs:
            age_val = float(res.outputs["age"])
            age_conf = float(res.outputs.get("age_confidence", res.confidence))
            state.demographics.age = age_val
            state.demographics.age_confidence = age_conf
            
            age_cap = state.get_capability_state(CapabilityId.AGE)
            age_cap.current_value = age_val
            age_cap.confidence = age_conf
            age_cap.last_seen_utc = time.time()
            age_cap.stabilization.ema_value = age_val

        if "gender" in res.outputs:
            g_val = str(res.outputs["gender"])
            g_conf = float(res.outputs.get("gender_confidence", res.confidence))
            state.demographics.gender = g_val
            state.demographics.gender_confidence = g_conf
            
            g_cap = state.get_capability_state(CapabilityId.GENDER)
            g_cap.current_value = g_val
            g_cap.confidence = g_conf
            g_cap.last_seen_utc = time.time()

        if "expression" in res.outputs:
            state.expression.primary_emotion = res.outputs["expression"]

        state.statistics.record_inference(latency_ms=res.execution_time_ms, quality_score=1.0, success=True)

    def purge_track(self, state: HumanState) -> None:
        """Handle track termination and purge stabilization buffers."""
        state.lifecycle = HumanStateLifecycle.TERMINATED
        self.stabilizer.purge_track(state.track_id)
        state.timeline.clear()
