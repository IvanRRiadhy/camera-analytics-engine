"""
PyTorch Inference Backend Implementation (Sprint H1.5A).

Concrete implementation of IInferenceBackend executing native PyTorch models on CUDA/CPU.
Supports model loading via safetensors/timm, FP16 half-precision execution, single-instance
session management, and warmup tensor execution.
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path
from typing import Any, Optional, Sequence
import numpy as np
import torch

from camera_analytics.bootstrap.resource_manager import RuntimeResourceManager

rm = RuntimeResourceManager.get_instance()
mivolo_path = rm.resolve("camera_analytics/third_party/MiVOLO")
if mivolo_path.exists() and str(mivolo_path.resolve()) not in sys.path:
    sys.path.insert(0, str(mivolo_path.resolve()))

from safetensors.torch import load_file
from mivolo.model.create_timm_model import create_model

from camera_analytics.core.human.inference_backend_base import IInferenceBackend
from camera_analytics.core.human.registry import ModelMetadata

logger = logging.getLogger(__name__)


class PyTorchBackend(IInferenceBackend):
    """Native PyTorch backend executing eager models on CUDA or CPU."""

    def __init__(self) -> None:
        self._model: Optional[torch.nn.Module] = None
        self._device: torch.device = torch.device("cpu")
        self._model_id: str = ""
        self._is_fp16: bool = False
        self._loaded: bool = False

    @property
    def backend_type(self) -> str:
        """Return backend identifier."""
        return "pytorch"

    def is_loaded(self) -> bool:
        """Return True if model session is initialized."""
        return self._loaded

    @property
    def device_name(self) -> str:
        """Return active compute device string."""
        return str(self._device)

    def initialize(self, metadata: ModelMetadata) -> bool:
        """Initialize session handles and allocate hardware memory."""
        weights_path = getattr(metadata, "weights_path", None) or "camera_analytics/models/human/mivolo/weights/model.safetensors"
        self.load(weights_path=weights_path, device=metadata.device, use_fp16=True, metadata={"model_id": metadata.model_id})
        return self._loaded

    def warmup(self) -> bool:
        """Execute dummy tensor inference to eliminate first-frame latency spikes."""
        if not self._loaded or self._model is None:
            return False
        dummy_inp = torch.zeros((1, 6, 384, 384), dtype=torch.float16 if self._is_fp16 else torch.float32, device=self._device)
        with torch.no_grad():
            _ = self._model(dummy_inp)
            if self._device.type == "cuda":
                torch.cuda.synchronize()
        return True

    def infer(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Execute neural inference given input dictionary."""
        inp_data = inputs.get("input") if "input" in inputs else next(iter(inputs.values()))
        output = self.predict(inp_data)
        return {"output": output}

    def load(
        self,
        weights_path: str,
        device: str = "cuda",
        use_fp16: bool = True,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """Load PyTorch model weights from safetensors file and initialize compute session."""
        if self._loaded:
            logger.info("[PyTorchBackend] Model '%s' already loaded. Reusing existing session.", self._model_id)
            return

        t0 = time.perf_counter()
        target_device = torch.device(device if torch.cuda.is_available() and str(device).startswith("cuda") else "cpu")
        self._device = target_device
        self._is_fp16 = use_fp16 and (target_device.type == "cuda")

        w_path = Path(weights_path)
        if not w_path.exists():
            raise FileNotFoundError(f"[PyTorchBackend] Model weights file not found: '{weights_path}'")

        # Load safetensors
        st_weights = load_file(str(w_path))
        clean_sd = {k.replace("mivolo.model.", ""): v for k, v in st_weights.items()}

        # Instantiate timm MiVOLO backbone
        model = create_model("mivolo_d1_384", pretrained=False, num_classes=3, in_chans=6)
        model.load_state_dict(clean_sd, strict=False)
        model.eval()

        if self._is_fp16:
            model.half()

        model.to(self._device)
        self._model = model
        self._loaded = True
        self._model_id = metadata.get("model_id", "mivolo_v2") if metadata else "mivolo_v2"

        load_ms = (time.perf_counter() - t0) * 1000.0
        logger.info(
            "[PyTorchBackend] Model '%s' loaded on device '%s' (FP16=%s) in %.2f ms.",
            self._model_id,
            self._device,
            self._is_fp16,
            load_ms,
        )

        # Warmup pass
        self.warmup()

    def predict(self, input_data: Any) -> Any:
        """Execute model forward pass.

        Args:
            input_data: Preprocessed input tensor (PyTorch Tensor or NumPy array [B, 6, 384, 384]).

        Returns:
            Raw PyTorch Tensor output [B, 3].
        """
        if not self._loaded or self._model is None:
            raise RuntimeError("[PyTorchBackend] predict() called before load().")

        if isinstance(input_data, np.ndarray):
            tensor_inp = torch.from_numpy(input_data)
        elif isinstance(input_data, torch.Tensor):
            tensor_inp = input_data
        else:
            raise TypeError(f"[PyTorchBackend] Unsupported input_data type: {type(input_data)}")

        tensor_inp = tensor_inp.to(self._device)
        if self._is_fp16 and tensor_inp.dtype == torch.float32:
            tensor_inp = tensor_inp.half()

        with torch.no_grad():
            output = self._model(tensor_inp)
            if self._device.type == "cuda":
                torch.cuda.synchronize()

        return output

    def unload(self) -> None:
        """Release PyTorch model memory resources."""
        if self._model is not None:
            del self._model
            self._model = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        self._loaded = False
        logger.info("[PyTorchBackend] Released PyTorch model session memory.")
