"""
Decoupled Neural Inference Backend Strategy Interface (IInferenceBackend).

Standardizes deep learning neural inference execution:
- PyTorchBackend: Production eager/TorchScript PyTorch engine (.safetensors / .pt).
- TensorRTBackend: Future Jetson/NVIDIA acceleration engine (.engine).
- ONNXBackend: Future cross-vendor engine (onnxruntime-gpu / .onnx).
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from camera_analytics.core.human.registry import ModelMetadata

logger = logging.getLogger(__name__)


class IInferenceBackend(ABC):
    """Abstract strategy interface for deep learning neural inference backends."""

    @property
    @abstractmethod
    def backend_type(self) -> str:
        """Return backend identifier (e.g. 'pytorch', 'tensorrt', 'onnx')."""
        pass

    @abstractmethod
    def is_loaded(self) -> bool:
        """Return True if model session is initialized."""
        pass

    @property
    @abstractmethod
    def device_name(self) -> str:
        """Return active compute device string."""
        pass

    @abstractmethod
    def initialize(self, metadata: ModelMetadata) -> bool:
        """Initialize session handles and allocate hardware memory."""
        pass

    @abstractmethod
    def warmup(self) -> bool:
        """Execute dummy tensor inference to eliminate first-frame latency spikes."""
        pass

    @abstractmethod
    def infer(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute neural inference given input dictionary."""
        pass
