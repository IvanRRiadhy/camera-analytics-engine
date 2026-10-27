"""
Decoupled Video & Inference Backend Strategy Factories for CCTV Analytics AI Engine.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from camera_analytics.core.human.inference_backend_base import IInferenceBackend
from camera_analytics.core.human.registry import ModelMetadata
from camera_analytics.core.video_backend import GStreamerBackend, IVideoBackend, OpenCVBackend
from camera_analytics.platform.capability_registry import RuntimeCapabilityRegistry

logger = logging.getLogger(__name__)


class VideoBackendFactory:
    """Factory creating IVideoBackend instances based on URI and system capabilities."""

    def __init__(self, capability_registry: Optional[RuntimeCapabilityRegistry] = None) -> None:
        self._capabilities = capability_registry

    def create_backend(self, source_uri: str, preferred_type: Optional[str] = None) -> IVideoBackend:
        """Create suitable IVideoBackend strategy.

        Args:
            source_uri: Video file path or RTSP stream URL.
            preferred_type: Optional backend override ('opencv', 'gstreamer').
        """
        ptype = (preferred_type or "").lower()

        if ptype == "gstreamer" or (
            self._capabilities and self._capabilities.has_capability("gstreamer") and source_uri.startswith("rtsp://")
        ):
            logger.info("VideoBackendFactory creating GStreamerBackend for: %s", source_uri)
            return GStreamerBackend()

        logger.info("VideoBackendFactory creating OpenCVBackend for: %s", source_uri)
        return OpenCVBackend()


class InferenceBackendFactory:
    """Factory creating IInferenceBackend instances based on model metadata and system capabilities."""

    def __init__(self, capability_registry: Optional[RuntimeCapabilityRegistry] = None) -> None:
        self._capabilities = capability_registry

    def create_backend(self, metadata: ModelMetadata, preferred_type: Optional[str] = None) -> IInferenceBackend:
        """Create suitable IInferenceBackend strategy.

        Args:
            metadata: Model metadata description.
            preferred_type: Optional backend override ('pytorch', 'tensorrt', 'onnx').
        """
        ptype = (preferred_type or "").lower()

        if ptype == "tensorrt" or (
            self._capabilities and self._capabilities.has_capability("tensorrt") and metadata.model_path.endswith(".engine")
        ):
            raise NotImplementedError("TensorRTBackend is scheduled for Jetson TensorRT Sprint")
        elif ptype == "onnx" or metadata.model_path.endswith(".onnx"):
            raise NotImplementedError("ONNXBackend is scheduled for ONNX Runtime Sprint")

        from camera_analytics.core.human.backends.pytorch_backend import PyTorchBackend
        logger.info("InferenceBackendFactory creating PyTorchBackend for model: %s", metadata.name)
        backend = PyTorchBackend()
        backend.initialize(metadata)
        return backend
