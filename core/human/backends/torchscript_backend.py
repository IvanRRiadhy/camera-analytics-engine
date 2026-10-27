"""
TorchScript Inference Backend Implementation (Sprint H1.5B).

Provides production GPU/CPU execution of TorchScript models (.pt / .torchscript.pt)
through the IInferenceBackend abstraction interface.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Optional
import torch

from camera_analytics.core.human.model_manager import IInferenceBackend
from camera_analytics.core.human.registry import ModelMetadata

logger = logging.getLogger(__name__)


class TorchScriptBackend(IInferenceBackend):
    """Production TorchScript model inference backend."""

    def __init__(self) -> None:
        self._model: Optional[torch.jit.ScriptModule] = None
        self._metadata: Optional[ModelMetadata] = None
        self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self._is_loaded = False

    def initialize(self, metadata: ModelMetadata) -> bool:
        """Initialize session handles and allocate hardware memory."""
        self._metadata = metadata
        self._device = torch.device(metadata.device if torch.cuda.is_available() and "cuda" in metadata.device else "cpu")
        weights_path = metadata.weights_path or "camera_analytics/models/human/mivolo/weights/mivolo_v2.torchscript.pt"
        self.load(model_path=weights_path, metadata=metadata, device=metadata.device)
        return True

    def warmup(self) -> bool:
        """Execute dummy tensor inference to eliminate first-frame latency spikes."""
        if not self._is_loaded or self._model is None or self._metadata is None:
            return False
        try:
            in_shape = self._metadata.input_shape or (1, 6, 384, 384)
            dummy_input = torch.randn(*in_shape, device=self._device)
            with torch.no_grad():
                _ = self._model(dummy_input)
                if self._device.type == "cuda":
                    torch.cuda.synchronize()
            return True
        except Exception as exc:
            logger.warning("[TorchScriptBackend] Warmup error: %s", exc)
            return False

    def load(self, model_path: str, metadata: ModelMetadata, device: str = "cuda:0") -> None:
        """Load TorchScript model from file path, configure device/precision, and execute warmup pass."""
        self._metadata = metadata
        self._device = torch.device(device if torch.cuda.is_available() and "cuda" in device else "cpu")
        
        path = Path(model_path)
        if not path.exists():
            raise FileNotFoundError(f"[TorchScriptBackend] Model weights file not found: '{model_path}'")

        logger.info("[TorchScriptBackend] Loading TorchScript model from '%s' on device '%s'...", path, self._device)
        self._model = torch.jit.load(str(path), map_location=self._device)
        self._model.eval()

        self._is_loaded = True

    def infer(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Execute TorchScript model forward pass.

        Args:
            inputs: Dictionary containing input tensor under key 'input' or 'input_tensor'.

        Returns:
            Dictionary containing output tensor under key 'output'.
        """
        if not self._is_loaded or self._model is None:
            raise RuntimeError("[TorchScriptBackend] Infer called before model was loaded.")

        tensor_in = inputs.get("input")
        if tensor_in is None:
            tensor_in = inputs.get("input_tensor")
        if tensor_in is None:
            raise KeyError("[TorchScriptBackend] Inputs dictionary missing 'input' or 'input_tensor' key.")

        if not isinstance(tensor_in, torch.Tensor):
            tensor_in = torch.from_numpy(tensor_in).to(self._device)
        elif tensor_in.device != self._device:
            tensor_in = tensor_in.to(self._device)

        with torch.no_grad():
            output_tensor = self._model(tensor_in)
            if self._device.type == "cuda":
                torch.cuda.synchronize()

        return {"output": output_tensor}

    def unload(self) -> None:
        """Release TorchScript model reference and free CUDA memory."""
        self._model = None
        self._is_loaded = False
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        logger.info("[TorchScriptBackend] Model unloaded and CUDA cache cleared.")

    def is_loaded(self) -> bool:
        return self._is_loaded
