"""
MiVOLO Attribute Decoder Implementation (Sprint H1.5B).

Concrete implementation of IAttributeDecoder parsing MiVOLO raw tensor outputs [B, 3] into
standardized HumanAttributes and model-agnostic InferenceResult DTOs.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional, Sequence
import numpy as np
import torch

from camera_analytics.core.human.decoder import HumanAttributes, IAttributeDecoder, InferenceResult

logger = logging.getLogger(__name__)


class MiVOLOAttributeDecoder(IAttributeDecoder):
    """Parses raw MiVOLO output vectors [B, 3] into HumanAttributes and InferenceResult DTOs.

    Index 0, 1: Gender logits [male_logit, female_logit]
    Index 2: Normalized age scalar
    """

    def __init__(self, min_age: float = 1.0, max_age: float = 95.0, avg_age: float = 45.0) -> None:
        self.min_age = min_age
        self.max_age = max_age
        self.avg_age = avg_age

    @property
    def module_id(self) -> str:
        """Return target module identifier."""
        return "mivolo_age_gender"

    def decode(
        self,
        raw_output: Any,
        request: Any,
        execution_time_ms: float = 0.0,
    ) -> InferenceResult:
        """Decode raw neural output into a standardized InferenceResult DTO."""
        t0 = time.time()
        
        # Extract numpy vector
        if isinstance(raw_output, dict):
            out_tensor = raw_output.get("output")
        else:
            out_tensor = raw_output

        if isinstance(out_tensor, torch.Tensor):
            out_arr = out_tensor.detach().cpu().numpy()
        else:
            out_arr = np.asarray(out_tensor)

        if len(out_arr.shape) == 2:
            pred_vec = out_arr[0]
        else:
            pred_vec = out_arr

        # 1. Decode Gender (idx 0, 1) via Softmax
        gender_logits = pred_vec[:2] if len(pred_vec) >= 2 else np.array([0.0, 0.0])
        exp_logits = np.exp(gender_logits - np.max(gender_logits))
        probs = exp_logits / np.sum(exp_logits)
        gender_idx = int(np.argmax(probs))
        predicted_gender = "male" if gender_idx == 0 else "female"
        gender_confidence = float(probs[gender_idx])

        # 2. Decode Age (idx 2) via official MiVOLO un-normalization
        if len(pred_vec) >= 3:
            raw_age_norm = float(pred_vec[2])
            unscaled_age = raw_age_norm * (self.max_age - self.min_age) + self.avg_age
            predicted_age = round(max(self.min_age, min(self.max_age, unscaled_age)), 1)
        else:
            predicted_age = 25.0
            raw_age_norm = 0.0

        attrs = HumanAttributes(
            age=predicted_age,
            gender=predicted_gender,
            confidence=gender_confidence,
            raw_outputs={
                "raw_age": raw_age_norm,
                "gender_logits": gender_logits.tolist(),
                "gender_probs": probs.tolist(),
            },
        )

        track_id = getattr(request, "track_id", 0)
        frame_idx = getattr(request, "frame_index", 0)

        return InferenceResult(
            track_id=track_id,
            module_id=self.module_id,
            attributes=attrs,
            confidence=gender_confidence,
            execution_time_ms=execution_time_ms,
            timestamp_utc=t0,
            status="SUCCESS",
        )
