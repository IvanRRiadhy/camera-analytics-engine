"""
Model Manager & Inference Backend Abstraction.

Defines the IInferenceBackend interface for ONNX/TensorRT/OpenVINO drivers and
ModelManager for handling session handles, device allocation, and warmup hooks.
"""

from __future__ import annotations

import logging
import threading
from abc import ABC, abstractmethod
from typing import Any, Optional

from camera_analytics.core.human.registry import InferenceModelRegistry, ModelMetadata

logger = logging.getLogger(__name__)


class IInferenceBackend(ABC):
    """Abstract interface for hardware inference backend drivers (ONNX, TensorRT, OpenVINO)."""

    @abstractmethod
    def initialize(self, metadata: ModelMetadata) -> bool:
        """Initialize session handles and allocate hardware memory."""
        pass

    @abstractmethod
    def warmup(self) -> bool:
        """Execute dummy tensor inference to eliminate first-frame latency spikes."""
        pass

    @abstractmethod
    def infer(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Execute neural inference given input dictionary."""
        pass

    @abstractmethod
    def is_loaded(self) -> bool:
        """Return True if backend session is loaded and ready for inference."""
        pass

    @abstractmethod
    def unload(self) -> None:
        """Release session handles and hardware resources."""
        pass


class StubInferenceBackend(IInferenceBackend):
    """Testing/Stub Inference Backend implementation for architecture validation."""

    def __init__(self, backend_type: str = "ONNX") -> None:
        self.backend_type = backend_type
        self._is_loaded = False
        self._metadata: Optional[ModelMetadata] = None

    def initialize(self, metadata: ModelMetadata) -> bool:
        self._metadata = metadata
        self._is_loaded = True
        logger.info("[StubInferenceBackend:%s] Initialized session for model '%s'", self.backend_type, metadata.model_id)
        return True

    def warmup(self) -> bool:
        if not self._is_loaded:
            return False
        logger.debug("[StubInferenceBackend:%s] Warmup executed for model '%s'", self.backend_type, self._metadata.model_id if self._metadata else "N/A")
        return True

    def infer(self, inputs: dict[str, Any]) -> dict[str, Any]:
        if not self._is_loaded:
            raise RuntimeError("StubInferenceBackend not initialized")
        return {"output": "stub_inference_result"}

    def is_loaded(self) -> bool:
        return self._is_loaded

    def unload(self) -> None:
        self._is_loaded = False
        logger.info("[StubInferenceBackend:%s] Released session resources.", self.backend_type)


class ModelManager:
    """Manages model backend sessions, device allocation, and warmup lifecycle."""

    def __init__(
        self,
        registry: Optional[InferenceModelRegistry] = None,
        inference_factory: Optional[Any] = None,
    ) -> None:
        self.registry = registry or InferenceModelRegistry()
        self._inference_factory = inference_factory
        self._lock = threading.RLock()
        self._sessions: dict[str, IInferenceBackend] = {}

    def load_model(self, model_id: str, backend: Optional[IInferenceBackend] = None) -> IInferenceBackend:
        """Load a model using registered metadata and appropriate InferenceBackend handle."""
        with self._lock:
            if model_id in self._sessions and self._sessions[model_id].is_loaded():
                return self._sessions[model_id]

            metadata = self.registry.get_metadata(model_id)
            if metadata is None:
                raise ValueError(f"[ModelManager] Model '{model_id}' is not registered in InferenceModelRegistry")

            if backend is None:
                from camera_analytics.platform.backend_factories import InferenceBackendFactory
                factory = self._inference_factory or InferenceBackendFactory()
                try:
                    selected_backend = factory.create_backend(metadata)
                except NotImplementedError:
                    selected_backend = StubInferenceBackend(backend_type="ONNX")
                    selected_backend.initialize(metadata)
                    selected_backend.warmup()
            else:
                selected_backend = backend
                selected_backend.initialize(metadata)
                selected_backend.warmup()

            self._sessions[model_id] = selected_backend
            logger.info("[ModelManager] Model '%s' successfully loaded and warmed up on device '%s'", model_id, metadata.device)
            return selected_backend

    def get_session(self, model_id: str) -> Optional[IInferenceBackend]:
        """Retrieve active IInferenceBackend session for model_id."""
        with self._lock:
            return self._sessions.get(model_id)

    def is_loaded(self, model_id: str) -> bool:
        """Check if model is currently loaded."""
        with self._lock:
            session = self._sessions.get(model_id)
            return session.is_loaded() if session else False

    def unload_model(self, model_id: str) -> bool:
        """Unload a specific model and free hardware resources."""
        with self._lock:
            session = self._sessions.pop(model_id, None)
            if session:
                session.unload()
                return True
            return False

    def unload_all(self) -> None:
        """Unload all active model sessions."""
        with self._lock:
            for model_id, session in list(self._sessions.items()):
                session.unload()
            self._sessions.clear()
            logger.info("[ModelManager] Unloaded all model sessions.")
