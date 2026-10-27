"""
Production MiVOLO Human Analytics AI Module (Sprint H1.5B).

Metadata-driven execution of TorchScript MiVOLO v2 model using ModelManager,
TorchScriptBackend, MiVOLOPreProcessor, and MiVOLOPostProcessor.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Optional
import numpy as np
from numpy.typing import NDArray

from camera_analytics.core.human.base_module import BaseHumanAnalyticsModule, ModuleConfig
from camera_analytics.core.human.context import HumanModuleContext, ModuleResult
from camera_analytics.core.human.models import HumanRepresentation, HumanState
from camera_analytics.core.human.model_manager import ModelManager
from camera_analytics.core.human.post_processors.mivolo_post_processor import MiVOLOPostProcessor
from camera_analytics.core.human.pre_processors.mivolo_pre_processor import MiVOLOPreProcessor
from camera_analytics.core.human.registry import ModelMetadata

logger = logging.getLogger(__name__)

METADATA_JSON_PATH = Path("camera_analytics/models/human/mivolo/metadata.json")


class MiVOLOModule(BaseHumanAnalyticsModule):
    """Production MiVOLO v2 AI Module performing TorchScript inference for Age and Gender."""

    def __init__(self, config: Optional[ModuleConfig] = None) -> None:
        # Load operational configuration dynamically from metadata.json
        self._meta_dict = self._load_metadata_dict()
        op_profile = self._meta_dict.get("operational_profile", {})
        
        cfg = config or ModuleConfig(
            enabled=True,
            priority=2,
            frame_stride=15,
            cooldown_s=0.5,
            minimum_face_quality=0.40,
            minimum_visibility=0.50,
            device=op_profile.get("verified_devices", ["cuda:0"])[0],
            provider=self._meta_dict.get("preferred_backend", "pytorch"),
        )
        super().__init__(config=cfg)

        self._meta = ModelMetadata(
            model_id=self._meta_dict.get("id", "mivolo_v2_age_gender"),
            name=self._meta_dict.get("name", "MiVOLO Multi-input Transformer"),
            version=self._meta_dict.get("version", "2.0.0"),
            capabilities=tuple(self._meta_dict.get("capabilities", ["age", "gender"])),
            device=self.config.device,
            provider=self.config.provider,
            preferred_backend=self._meta_dict.get("preferred_backend", "pytorch"),
            input_shape=tuple(self._meta_dict.get("input_specification", {}).get("tensor_shape", [1, 6, 384, 384])),
            description=self._meta_dict.get("description", "Certified production PyTorch build of MiVOLO v2."),
        )

        in_res = tuple(self._meta_dict.get("input_specification", {}).get("input_resolution", [384, 384]))
        norm_mean = tuple(self._meta_dict.get("input_specification", {}).get("normalization", {}).get("mean", [0.485, 0.456, 0.406, 0.485, 0.456, 0.406]))
        norm_std = tuple(self._meta_dict.get("input_specification", {}).get("normalization", {}).get("std", [0.229, 0.224, 0.225, 0.229, 0.224, 0.225]))

        self.pre_processor = MiVOLOPreProcessor(input_resolution=in_res, mean=norm_mean, std=norm_std, device=self.config.device)
        self.post_processor = MiVOLOPostProcessor()
        self._model_manager: Optional[ModelManager] = None

    def _load_metadata_dict(self) -> dict[str, Any]:
        """Read metadata.json from disk."""
        if METADATA_JSON_PATH.exists():
            try:
                with open(METADATA_JSON_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as exc:
                logger.warning("[MiVOLOModule] Could not parse metadata.json: %s", exc)
        return {}

    @property
    def module_id(self) -> str:
        return "mivolo_age_gender"

    @property
    def metadata(self) -> ModelMetadata:
        return self._meta

    def initialize(self, model_manager: ModelManager) -> None:
        """Register model metadata and load model handle via ModelManager."""
        self._model_manager = model_manager
        self._model_manager.registry.register_model(self._meta)
        self._model_manager.load_model(self._meta.model_id)
        self._is_initialized = True
        logger.info("[MiVOLOModule] Production TorchScript AI module initialized successfully.")

    def process_batch(self, contexts: list[HumanModuleContext]) -> list[ModuleResult]:
        """Execute real TorchScript MiVOLO v2 AI inference pipeline for a batch of track contexts."""
        if not contexts or not self._is_initialized or self._model_manager is None:
            return []

        # 1. Preprocessing (Crop assembly, resizing to 384x384, normalization, GPU tensor transfer)
        batch_tensor, pre_lat = self.pre_processor.preprocess_batch(contexts)

        # 2. GPU Model Inference via ModelManager (PyTorch or TorchScript)
        t_infer_0 = time.perf_counter()
        session = self._model_manager.get_session(self._meta.model_id)
        if session is None:
            raise RuntimeError(f"[MiVOLOModule] Inference session for model '{self._meta.model_id}' is not loaded.")

        if hasattr(session, "predict"):
            raw_output_dict = session.predict(batch_tensor)
        else:
            raw_output_dict = session.infer({"input": batch_tensor})
        infer_lat = (time.perf_counter() - t_infer_0) * 1000.0

        # 3. Postprocessing (Raw output logits parsing -> age float + gender string ModuleResults)
        results, post_lat = self.post_processor.postprocess_batch(
            raw_output=raw_output_dict,
            contexts=contexts,
            module_id=self.module_id,
        )

        total_lat = pre_lat + infer_lat + post_lat
        avg_track_lat = round(total_lat / len(contexts), 3) if contexts else 0.0

        for r in results:
            object.__setattr__(r, "execution_time_ms", avg_track_lat)

        return results

    def process(
        self,
        representation: HumanRepresentation,
        state: HumanState,
        frame: Optional[NDArray[np.uint8]] = None,
        runtime_context: Optional[Any] = None,
    ) -> HumanState:
        """Single-track fallback wrapper."""
        ctx = HumanModuleContext(representation=representation, state=state, frame=frame, runtime_context=runtime_context)
        results = self.process_batch([ctx])
        if results and "age" in results[0].outputs:
            state.demographics.age = results[0].outputs["age"]
            state.demographics.gender = results[0].outputs["gender"]
        return state

    def update_state(self, state: HumanState, inference_output: Any) -> HumanState:
        return state

    def cleanup(self) -> None:
        self._is_initialized = False
