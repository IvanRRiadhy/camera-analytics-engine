"""
MiVOLO Image & Crop Pre-Processor (Sprint H1.5B).

Prepares 6-channel dual face+person input tensors for TorchScript MiVOLO model execution.
Extracted into IPreProcessor abstraction to satisfy SRP and OCP.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Optional, Sequence
import cv2
import numpy as np
import torch
from numpy.typing import NDArray

from camera_analytics.core.human.context import HumanModuleContext

logger = logging.getLogger(__name__)


class IPreProcessor(ABC):
    """Abstract interface for vision input pre-processors."""

    @abstractmethod
    def preprocess_batch(self, contexts: Sequence[HumanModuleContext]) -> tuple[torch.Tensor, float]:
        """Convert a batch of track contexts into a PyTorch batch tensor.

        Returns:
            Tuple of (batch_tensor, preprocess_latency_ms).
        """
        pass


class MiVOLOPreProcessor(IPreProcessor):
    """Assembles 6-channel face+body input tensors for MiVOLO v2 (384x384 input resolution)."""

    def __init__(
        self,
        input_resolution: tuple[int, int] = (224, 224),
        mean: tuple[float, ...] = (0.485, 0.456, 0.406, 0.485, 0.456, 0.406),
        std: tuple[float, ...] = (0.229, 0.224, 0.225, 0.229, 0.224, 0.225),
        device: str = "cuda",
    ) -> None:
        self.target_w, self.target_h = input_resolution
        self.mean = np.array(mean, dtype=np.float32).reshape(1, 1, 6)
        self.std = np.array(std, dtype=np.float32).reshape(1, 1, 6)
        self.device = torch.device(device if torch.cuda.is_available() and "cuda" in device else "cpu")

    def _prepare_crop(self, crop: Optional[NDArray[np.uint8]]) -> NDArray[np.float32]:
        """Resize crop to target resolution and normalize to float32 [0, 1]."""
        if crop is None or crop.size == 0:
            resized = np.zeros((self.target_h, self.target_w, 3), dtype=np.uint8)
        else:
            resized = cv2.resize(crop, (self.target_w, self.target_h), interpolation=cv2.INTER_LINEAR)
            if len(resized.shape) == 2:
                resized = cv2.cvtColor(resized, cv2.COLOR_GRAY2BGR)
            elif resized.shape[2] == 4:
                resized = cv2.cvtColor(resized, cv2.COLOR_BGRA2BGR)
            # Convert BGR to RGB
            resized = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)

        return resized.astype(np.float32) / 255.0

    def preprocess_batch(self, contexts: Sequence[HumanModuleContext]) -> tuple[torch.Tensor, float]:
        """Assemble 6-channel batch tensor (B, 6, H, W)."""
        t0 = time.perf_counter()
        batch_list = []

        for ctx in contexts:
            if hasattr(ctx, "crop_handle"):
                face_crop = ctx.crop_handle.face_crop
                body_crop = ctx.crop_handle.body_crop
            elif hasattr(ctx, "representation"):
                crop_cache = ctx.representation.crop_cache
                face_crop = crop_cache.face_crop
                body_crop = crop_cache.body_crop if crop_cache.body_crop is not None else (crop_cache.head_crop if crop_cache.head_crop is not None else crop_cache.torso_crop)
            else:
                crop_cache = getattr(ctx, "crop_cache", None)
                face_crop = crop_cache.face_crop if crop_cache else None
                body_crop = (crop_cache.body_crop if crop_cache.body_crop is not None else (crop_cache.head_crop if crop_cache.head_crop is not None else crop_cache.torso_crop)) if crop_cache else None

            face_img = self._prepare_crop(face_crop)
            body_img = self._prepare_crop(body_crop)

            # Concatenate along channel axis -> (384, 384, 6)
            dual_img = np.concatenate([face_img, body_img], axis=2)
            # Normalize: (dual_img - mean) / std
            normalized = (dual_img - self.mean) / self.std
            # Transpose HWC to CHW -> (6, 384, 384)
            chw = np.transpose(normalized, (2, 0, 1))
            batch_list.append(chw)

        if not batch_list:
            empty_tensor = torch.zeros((0, 6, self.target_h, self.target_w), dtype=torch.float32, device=self.device)
            return empty_tensor, 0.0

        batch_arr = np.stack(batch_list, axis=0)  # (B, 6, 384, 384)
        tensor = torch.from_numpy(batch_arr).to(self.device)
        lat_ms = (time.perf_counter() - t0) * 1000.0

        return tensor, round(lat_ms, 3)
