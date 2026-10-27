"""
RuntimeCapabilityRegistry for CCTV Analytics AI Engine.

Tracks boolean hardware capabilities and environment metadata:
- Capabilities: 'cuda', 'gstreamer', 'tensorrt', 'studio_gui', 'mqtt', 'rabbitmq', 'viewer'
- Metadata: 'cuda_version', 'pytorch_version', 'opencv_version', 'gpu_name', 'compute_capability'
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Set

logger = logging.getLogger(__name__)


class RuntimeCapabilityRegistry:
    """Registry managing platform capabilities and diagnostic environment metadata."""

    def __init__(self) -> None:
        self._capabilities: Set[str] = set()
        self._metadata: Dict[str, Any] = {}

    def register_capability(self, name: str) -> None:
        """Register a boolean capability flag."""
        self._capabilities.add(name.lower())
        logger.debug("Capability registered: '%s'", name)

    def has_capability(self, name: str) -> bool:
        """Return True if capability is supported."""
        return name.lower() in self._capabilities

    def set_metadata(self, key: str, value: Any) -> None:
        """Store metadata key-value pair."""
        self._metadata[key] = value

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Retrieve metadata value."""
        return self._metadata.get(key, default)

    def get_all_capabilities(self) -> Set[str]:
        """Return copy of all registered capabilities."""
        return set(self._capabilities)

    def get_all_metadata(self) -> Dict[str, Any]:
        """Return copy of all metadata."""
        return dict(self._metadata)
