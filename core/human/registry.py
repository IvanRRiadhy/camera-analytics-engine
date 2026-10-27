"""
Inference Model Registry.

Manages model metadata registration, capability discovery, input/output schemas,
and versioning without loading weights automatically.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ModelMetadata:
    """Metadata describing an AI inference model registered in the system."""

    model_id: str
    name: str
    version: str
    capabilities: tuple[str, ...] = ()    # e.g. ("age", "gender"), ("emotion",), ("face_embedding",)
    device: str = "cuda:0"
    provider: str = "CUDAExecutionProvider"
    preferred_backend: str = "torchscript"
    weights_path: Optional[str] = None
    input_shape: tuple[int, ...] = (1, 6, 384, 384)
    output_schema: dict[str, Any] = field(default_factory=dict)
    description: str = ""


class InferenceModelRegistry:
    """Centralized registry for AI model metadata and capability discovery."""

    def __init__(self) -> None:
        self._models: dict[str, ModelMetadata] = {}

    def register_model(self, metadata: ModelMetadata) -> None:
        """Register a model's metadata in the registry."""
        if metadata.model_id in self._models:
            logger.warning("[InferenceModelRegistry] Overwriting existing model registration for '%s'", metadata.model_id)
        self._models[metadata.model_id] = metadata
        logger.info(
            "[InferenceModelRegistry] Registered model '%s' (v%s) | Capabilities: %s | Provider: %s",
            metadata.model_id,
            metadata.version,
            metadata.capabilities,
            metadata.provider,
        )

    def get_metadata(self, model_id: str) -> Optional[ModelMetadata]:
        """Retrieve ModelMetadata by model_id."""
        return self._models.get(model_id)

    def find_models_by_capability(self, capability: str) -> list[ModelMetadata]:
        """Discover models offering a specific capability (e.g., 'age', 'gender', 'emotion', 'face_embedding')."""
        cap_lower = capability.lower().strip()
        matched = [
            meta for meta in self._models.values()
            if any(c.lower().strip() == cap_lower for c in meta.capabilities)
        ]
        return matched

    def list_models(self) -> list[ModelMetadata]:
        """List all registered model metadata entries."""
        return list(self._models.values())

    def unregister_model(self, model_id: str) -> bool:
        """Remove a model from the registry."""
        if model_id in self._models:
            del self._models[model_id]
            return True
        return False

    def clear(self) -> None:
        """Clear all registered models."""
        self._models.clear()
