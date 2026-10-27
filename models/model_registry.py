"""
Model Registry component for CCTV Analytics AI Engine.

Manages model metadata inventory, querying platform-compatible weights for packaging and Docker image layer bundling.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from camera_analytics.bootstrap.resource_manager import RuntimeResourceManager

logger = logging.getLogger(__name__)


@dataclass
class ModelMetadata:
    """Model metadata payload."""

    model_id: str
    category: str
    model_name: str
    filename: str
    size_bytes: int
    supported_platforms: List[str]
    supported_backends: List[str]
    required: bool


class ModelRegistry:
    """Registry managing model metadata and platform model requirements."""

    _instance: Optional[ModelRegistry] = None

    def __init__(self) -> None:
        self.rm = RuntimeResourceManager.get_instance()
        self._models: Dict[str, ModelMetadata] = {}
        self.reload()

    @classmethod
    def get_instance(cls) -> ModelRegistry:
        """Singleton accessor for ModelRegistry."""
        if cls._instance is None:
            cls._instance = ModelRegistry()
        return cls._instance

    def reload(self) -> None:
        """Reload models registry from configs/models.json."""
        registry_file = self.rm.resolve("configs/models.json")
        if not registry_file.exists():
            logger.warning("[ModelRegistry] Registry file missing: %s", registry_file)
            return

        with open(registry_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        self._models.clear()
        for item in data.get("models", []):
            meta = ModelMetadata(
                model_id=item["model_id"],
                category=item["category"],
                model_name=item["model_name"],
                filename=item["filename"],
                size_bytes=item["size_bytes"],
                supported_platforms=item.get("supported_platforms", []),
                supported_backends=item.get("supported_backends", []),
                required=item.get("required", True),
            )
            self._models[meta.model_id] = meta

    def get_models_for_profile(self, platform_name: str, backend_name: str = "pytorch") -> List[ModelMetadata]:
        """Query models required for a specific platform profile.

        Args:
            platform_name: Target platform (e.g., 'jetson_nano', 'windows', 'docker')
            backend_name: Active inference backend (e.g., 'pytorch')

        Returns:
            List[ModelMetadata]: Required model metadata entries.
        """
        result: List[ModelMetadata] = []
        for model in self._models.values():
            if platform_name in model.supported_platforms or "all" in model.supported_platforms or "docker" in model.supported_platforms:
                if backend_name in model.supported_backends or "all" in model.supported_backends:
                    result.append(model)
        return result
