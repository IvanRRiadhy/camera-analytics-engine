"""
HumanState Presenter & View Model Layer (Sprint H1.5C).

Maps persistent HumanState domain models into presentation HumanStateViewModel objects,
decoupling Standalone Viewer rendering logic from internal domain entity structures.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

from camera_analytics.core.human.models import CapabilityId, HumanState, HumanStateLifecycle
from camera_analytics.logging import RuntimeLogger

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class CapabilityViewModel:
    """Presentation view model for a single capability."""

    capability_id: str
    current_value: Any
    confidence: float
    lock_state: str
    ema_value: Optional[float] = None
    inference_count: int = 0


@dataclass(slots=True)
class HumanStateViewModel:
    """Presentation view model for a persistent tracked person state."""

    track_id: int
    lifecycle: str
    track_lifetime_s: float
    first_seen_formatted: str
    last_seen_formatted: str
    total_inference_count: int
    skipped_count: int
    average_quality_score: float
    last_latency_ms: float
    timeline_length: int
    capabilities: list[CapabilityViewModel] = field(default_factory=list)

    @property
    def gender(self) -> str:
        for cap in self.capabilities:
            if cap.capability_id.lower() == "gender" and cap.current_value is not None:
                return str(cap.current_value)
        return "unknown"

    @property
    def gender_confidence(self) -> float:
        for cap in self.capabilities:
            if cap.capability_id.lower() == "gender":
                return float(cap.confidence)
        return 0.0

    @property
    def age(self) -> float:
        for cap in self.capabilities:
            if cap.capability_id.lower() == "age" and cap.current_value is not None:
                return float(cap.current_value)
        return 0.0

    @property
    def ema_age(self) -> float:
        for cap in self.capabilities:
            if cap.capability_id.lower() == "age" and cap.ema_value is not None:
                return float(cap.ema_value)
        return self.age

    @property
    def face_quality_score(self) -> float:
        return self.average_quality_score


class HumanStatePresenter:
    """Presenter mapping domain HumanState objects to HumanStateViewModel view models."""

    @staticmethod
    def present(state: HumanState) -> HumanStateViewModel:
        """Map a single HumanState object into a HumanStateViewModel."""
        cap_vms = []
        for cap_id, cap_state in state.capabilities.items():
            cap_vms.append(
                CapabilityViewModel(
                    capability_id=cap_id.value if isinstance(cap_id, CapabilityId) else str(cap_id),
                    current_value=cap_state.current_value,
                    confidence=round(cap_state.confidence, 2),
                    lock_state=cap_state.stabilization.lock_state,
                    ema_value=round(cap_state.stabilization.ema_value, 1) if cap_state.stabilization.ema_value is not None else None,
                    inference_count=cap_state.inference_count,
                )
            )

        t_first = time.strftime("%H:%M:%S", time.localtime(state.first_seen_utc))
        t_last = time.strftime("%H:%M:%S", time.localtime(state.last_seen_utc))

        vm = HumanStateViewModel(
            track_id=state.track_id,
            lifecycle=state.lifecycle.value if isinstance(state.lifecycle, HumanStateLifecycle) else str(state.lifecycle),
            track_lifetime_s=state.track_lifetime_s,
            first_seen_formatted=t_first,
            last_seen_formatted=t_last,
            total_inference_count=state.statistics.inference_count,
            skipped_count=state.statistics.skipped_count,
            average_quality_score=state.statistics.average_quality_score,
            last_latency_ms=round(state.statistics.last_inference_latency_ms, 1),
            timeline_length=len(state.timeline),
            capabilities=cap_vms,
        )

        import threading
        RuntimeLogger.forensic(
            logger,
            "[FORENSIC STAGE 9 - PRESENTER] Thread: %d | TrackID: %d | Gender: %s (%d%%) | EMAAge: %.1fy | Lifecycle: %s",
            threading.get_ident(),
            vm.track_id,
            vm.gender,
            int(vm.gender_confidence * 100),
            vm.ema_age,
            vm.lifecycle,
        )

        return vm
