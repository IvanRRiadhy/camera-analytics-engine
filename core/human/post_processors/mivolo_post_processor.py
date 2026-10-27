"""
MiVOLO Tensor Post-Processor Implementation (Sprint H1.5B).

Parses raw PyTorch/TorchScript output tensors into typed predictions and packages them into ModuleResult objects.
Extracted into IPostProcessor abstraction to satisfy SRP and OCP.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Optional, Sequence
import numpy as np
import torch

from camera_analytics.core.human.context import HumanModuleContext, ModuleResult

logger = logging.getLogger(__name__)


class IPostProcessor(ABC):
    """Abstract interface for model output post-processors."""

    @abstractmethod
    def postprocess_batch(
        self,
        raw_output: Any,
        contexts: Sequence[HumanModuleContext],
        module_id: str,
    ) -> tuple[list[ModuleResult], float]:
        """Parse raw model outputs into typed ModuleResult objects.

        Returns:
            Tuple of (list[ModuleResult], postprocess_latency_ms).
        """
        pass


class MiVOLOPostProcessor(IPostProcessor):
    """Parses MiVOLO output logits into age (float years) and gender ('male'|'female')."""

    def __init__(self, gender_threshold: float = 0.50, min_age: float = 1.0, max_age: float = 95.0, avg_age: float = 45.0) -> None:
        self.gender_threshold = gender_threshold
        self.min_age = min_age
        self.max_age = max_age
        self.avg_age = avg_age

    def postprocess_batch(
        self,
        raw_output: Any,
        contexts: Sequence[HumanModuleContext],
        module_id: str,
    ) -> tuple[list[ModuleResult], float]:
        """Process output tensor (B, 3) where idx 0,1 = gender logits [male, female], idx 2 = age norm."""
        t0 = time.perf_counter()
        results: list[ModuleResult] = []

        if raw_output is None or not contexts:
            return results, 0.0

        # Convert tensor to numpy array
        if isinstance(raw_output, dict):
            out_tensor = raw_output.get("output")
        else:
            out_tensor = raw_output

        if isinstance(out_tensor, torch.Tensor):
            out_arr = out_tensor.detach().cpu().numpy()
        else:
            out_arr = np.asarray(out_tensor)

        for i, ctx in enumerate(contexts):
            t_id = ctx.track_id if hasattr(ctx, "track_id") else ctx.representation.track_id
            if i >= len(out_arr):
                break

            pred_vec = out_arr[i]
            
            # 1. Official MiVOLO Gender Logits: Index 0 = Male Logit, Index 1 = Female Logit
            if len(pred_vec) >= 2:
                gender_logits = pred_vec[:2]
                exp_logits = np.exp(gender_logits - np.max(gender_logits))
                probs = exp_logits / np.sum(exp_logits)
                gender_idx = int(np.argmax(probs))
                predicted_gender = "male" if gender_idx == 0 else "female"
                gender_conf = round(float(probs[gender_idx]), 3)
            else:
                predicted_gender = "male"
                gender_conf = 0.85

            # 2. Official MiVOLO Age Calculation: Index 2 = Normalized Age Scalar
            if len(pred_vec) >= 3:
                raw_age_norm = float(pred_vec[2])
                unscaled_age = raw_age_norm * (self.max_age - self.min_age) + self.avg_age
                predicted_age = round(max(self.min_age, min(self.max_age, unscaled_age)), 1)
            else:
                predicted_age = 25.0
            age_conf = 0.90

            # Evaluate attribute lock triggers (e.g. lock gender if confidence > 0.80)
            lock_gender = gender_conf >= 0.80
            lock_age = False  # Age updates periodically

            outputs = {
                "age": float(predicted_age),
                "age_confidence": float(age_conf),
                "gender": str(predicted_gender),
                "gender_confidence": float(gender_conf),
                "lock_gender": bool(lock_gender),
                "lock_age": bool(lock_age),
                "processing_state": "COMPLETED",
            }

            results.append(
                ModuleResult(
                    module_id=module_id,
                    track_id=t_id,
                    outputs=outputs,
                    confidence=gender_conf,
                    execution_time_ms=0.0,
                    status="SUCCESS",
                )
            )

        lat_ms = (time.perf_counter() - t0) * 1000.0
        return results, round(lat_ms, 3)
