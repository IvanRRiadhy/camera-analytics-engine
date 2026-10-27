"""
Human Runtime Facade & Subsystem Coordinator.

Orchestrates HumanRepresentationExtractor, FaceQualityEstimator, and HumanStateCache,
returning a decoupled HumanRuntimeResult per frame.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence
import numpy as np
from numpy.typing import NDArray

from camera_analytics.core.human.cache import HumanStateCache
from camera_analytics.core.human.models import HumanRepresentation, HumanState
from camera_analytics.core.human.model_manager import ModelManager
from camera_analytics.core.human.registry import InferenceModelRegistry
from camera_analytics.core.human.representation_extractor import HumanRepresentationExtractor
from camera_analytics.core.human.scheduler import HumanAnalyticsScheduler

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class HumanRuntimeResult:
    """Decoupled output of the Human Runtime subsystem execution per frame."""

    representations: dict[int, HumanRepresentation] = field(default_factory=dict)
    states: dict[int, HumanState] = field(default_factory=dict)
    summary: dict[str, Any] = field(default_factory=dict)
    elapsed_ms: float = 0.0


class HumanRuntime:
    """Facade orchestrating human representation extraction, quality estimation, DAG scheduling, and state caching."""

    def __init__(
        self,
        cache: Optional[HumanStateCache] = None,
        model_manager: Optional[ModelManager] = None,
        scheduler: Optional[HumanAnalyticsScheduler] = None,
    ) -> None:
        self.cache = cache or HumanStateCache()
        self.extractor = HumanRepresentationExtractor()
        self.registry = InferenceModelRegistry()
        self.model_manager = model_manager or ModelManager(registry=self.registry)
        self.scheduler = scheduler or HumanAnalyticsScheduler(model_manager=self.model_manager)
        
        # Auto-register production MiVOLO Age/Gender AI Module
        try:
            from camera_analytics.core.human.modules.mivolo_module import MiVOLOModule
            mivolo = MiVOLOModule()
            self.scheduler.register_module(mivolo)
            logger.info("[HumanRuntime] Auto-registered 'mivolo_age_gender' AI module in HumanAnalyticsScheduler DAG graph.")
        except Exception as exc:
            logger.warning("[HumanRuntime] Could not auto-register MiVOLOModule: %s", exc)

    def process_frame(
        self,
        tracks: list[dict[str, Any]],
        frame: Optional[NDArray[np.uint8]] = None,
        frame_index: int = 0,
        timestamp_utc: float = 0.0,
        runtime_context: Optional[Any] = None,
    ) -> HumanRuntimeResult:
        """Process active tracks for a frame and update human domain representations and state cache."""
        start_t = time.perf_counter()
        active_track_ids: set[int] = set()
        representations: dict[int, HumanRepresentation] = {}
        states: dict[int, HumanState] = {}

        total_quality = 0.0
        quality_count = 0

        for track in tracks:
            t_id = int(track.get("track_id", 1))
            active_track_ids.add(t_id)

            # 1. Extract non-inference HumanRepresentation & ROICropCache
            rep = self.extractor.extract(
                track=track,
                frame=frame,
                frame_index=frame_index,
                timestamp_utc=timestamp_utc,
            )
            representations[t_id] = rep

            # 2. Retrieve or initialize HumanState from cache
            initial_state = self.cache.get_or_create(t_id)

            # 3. Execute Scheduler DAG for registered AI modules
            enriched_state = self.scheduler.execute_pipeline(
                representation=rep,
                state=initial_state,
                frame=frame,
                runtime_context=runtime_context,
                frame_index=frame_index,
                timestamp=timestamp_utc,
            )

            self.cache.update(enriched_state)
            states[t_id] = enriched_state

            # Track quality statistics
            if rep.face_quality_score > 0.0:
                total_quality += rep.face_quality_score
                quality_count += 1

        # 4. Purge inactive/expired tracks from cache
        self.cache.purge_expired(active_track_ids)

        # 5. Construct Telemetry Summary
        avg_quality = round(total_quality / quality_count, 3) if quality_count > 0 else 0.0
        summary = {
            "totalTracked": len(active_track_ids),
            "averageFaceQuality": avg_quality,
            "moduleMetrics": self.scheduler.get_metrics_summary(),
        }

        elapsed_ms = (time.perf_counter() - start_t) * 1000.0

        return HumanRuntimeResult(
            representations=representations,
            states=states,
            summary=summary,
            elapsed_ms=round(elapsed_ms, 2),
        )

    def cleanup(self) -> None:
        """Shutdown scheduler modules and unload model manager."""
        self.scheduler.cleanup()
        self.cache.clear()
