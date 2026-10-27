"""
Base Human Analytics Module.

Defines the abstract base class and configuration structure for all future Human Analytics
AI modules (MiVOLO, Emotion, ArcFace, PPE, etc.).
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence
import numpy as np
from numpy.typing import NDArray

from camera_analytics.core.human.models import HumanRepresentation, HumanState
from camera_analytics.core.human.model_manager import ModelManager
from camera_analytics.core.human.registry import ModelMetadata

logger = logging.getLogger(__name__)


@dataclass
class ModuleConfig:
    """Configuration options for a Human Analytics AI module."""

    enabled: bool = True
    priority: int = 3
    frame_stride: int = 15
    cooldown_s: float = 0.5
    minimum_face_quality: float = 0.35
    minimum_visibility: float = 0.50
    quality_delta: float = 0.15
    device: str = "cuda:0"
    provider: str = "CUDAExecutionProvider"
    extra_params: dict[str, Any] = field(default_factory=dict)


class BaseHumanAnalyticsModule(ABC):
    """Abstract Base Class for all Human Analytics AI modules."""

    def __init__(self, config: Optional[ModuleConfig] = None) -> None:
        self.config = config or ModuleConfig()
        self._is_initialized = False

    @property
    @abstractmethod
    def module_id(self) -> str:
        """Unique module identifier (e.g., 'mivolo_age_gender', 'hsemotion', 'arcface')."""
        pass

    @property
    @abstractmethod
    def metadata(self) -> ModelMetadata:
        """Return ModelMetadata describing this module's AI capabilities and schema."""
        pass

    @abstractmethod
    def initialize(self, model_manager: ModelManager) -> None:
        """Initialize module, load backend models via ModelManager, and register metadata."""
        pass

    def should_process(
        self,
        representation: HumanRepresentation,
        state: HumanState,
        frame_index: int = 0,
        timestamp: float = 0.0,
    ) -> bool:
        """Evaluate multi-condition triggers (frame stride, quality gate, lock status)."""
        if not self.config.enabled:
            return False

        # Lock status check
        if state.is_locked:
            return False

        # Frame Stride check (always process first frame for new tracks, or on stride intervals)
        is_first_inference = (state.statistics.inference_count == 0)
        if self.config.frame_stride > 1 and not is_first_inference and (frame_index % self.config.frame_stride != 0):
            return False

        # Minimum Face Quality gate
        if representation.face_quality_score < self.config.minimum_face_quality:
            return False

        # Minimum Keypoint Visibility gate
        if representation.visibility_score < self.config.minimum_visibility:
            return False

        return True

    @abstractmethod
    def process(
        self,
        representation: HumanRepresentation,
        state: HumanState,
        frame: Optional[NDArray[np.uint8]] = None,
        runtime_context: Optional[Any] = None,
    ) -> HumanState:
        """Execute module processing and return updated HumanState."""
        pass

    @abstractmethod
    def update_state(self, state: HumanState, inference_output: Any) -> HumanState:
        """Enrich HumanState with inference results."""
        pass

    def process_batch(self, contexts: Sequence[Any]) -> list[Any]:
        """Default fallback batch processing delegating to self.process()."""
        from camera_analytics.core.human.context import ModuleResult
        results: list[ModuleResult] = []
        for ctx in contexts:
            t0 = time.perf_counter()
            up_state = self.process(
                representation=ctx.representation,
                state=ctx.state,
                frame=ctx.frame,
                runtime_context=ctx.runtime_context,
            )
            lat = (time.perf_counter() - t0) * 1000.0
            # Extract outputs if updated directly in custom_attributes by legacy/test modules
            outputs = up_state.custom_attributes.get(self.module_id, {})
            if isinstance(outputs, dict) and "outputs" in outputs:
                outputs = outputs["outputs"]
            results.append(
                ModuleResult(
                    module_id=self.module_id,
                    track_id=ctx.representation.track_id,
                    outputs=outputs if isinstance(outputs, dict) else {"executed": True},
                    execution_time_ms=lat,
                    status="SUCCESS",
                )
            )
        return results

    @abstractmethod
    def cleanup(self) -> None:
        """Release resources on shutdown."""
        pass
