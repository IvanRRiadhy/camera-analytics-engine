"""
Abstract RuntimePlatform Base Class for CCTV Analytics AI Engine.

Defines OS-agnostic and hardware-agnostic platform interfaces & lifecycle methods:
- Lifecycle: initialize(), verify_environment(), shutdown(), cleanup()
- Capability Registration
- OS Signal Handling & Multiprocessing Safety
"""

from __future__ import annotations

import logging
import signal
import sys
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Optional

from camera_analytics.bootstrap.resource_manager import RuntimeResourceManager
from camera_analytics.platform.capability_registry import RuntimeCapabilityRegistry

logger = logging.getLogger(__name__)


class RuntimePlatform(ABC):
    """Abstract base class representing an operating environment (OS / Target Hardware)."""

    def __init__(self) -> None:
        self._is_initialized: bool = False
        self._capabilities: RuntimeCapabilityRegistry = RuntimeCapabilityRegistry()

    @property
    @abstractmethod
    def name(self) -> str:
        """Return platform identifier name (e.g. 'windows', 'linux', 'jetson', 'docker')."""
        pass

    @property
    @abstractmethod
    def target_environment(self) -> str:
        """Return target environment code (e.g. 'WIN_X64', 'LINUX_X64', 'JETSON_ARM64', 'DOCKER_CONTAINER')."""
        pass

    @property
    def capabilities(self) -> RuntimeCapabilityRegistry:
        """Return capability registry for this platform."""
        return self._capabilities

    def get_resource_manager(self) -> RuntimeResourceManager:
        """Return centralized RuntimeResourceManager instance."""
        return RuntimeResourceManager.get_instance()

    def initialize(self) -> None:
        """Lifecycle hook: Initialize platform capabilities and metadata."""
        if self._is_initialized:
            return
        self.setup_multiprocessing()
        self.audit_hardware()
        self._is_initialized = True
        logger.info("[+] Platform '%s' (%s) initialized successfully.", self.name, self.target_environment)

    def verify_environment(self) -> bool:
        """Lifecycle hook: Validate environment integrity."""
        return self._is_initialized

    def shutdown(self) -> None:
        """Lifecycle hook: Gracefully stop platform services."""
        logger.info("[+] Platform '%s' shutdown completed.", self.name)

    def cleanup(self) -> None:
        """Lifecycle hook: Free hardware handles."""
        self._is_initialized = False
        logger.info("[+] Platform '%s' cleanup completed.", self.name)

    def setup_multiprocessing(self) -> None:
        """Initialize multiprocessing safety (freeze_support on Windows, no-op on POSIX)."""
        if getattr(sys, "frozen", False) and sys.platform == "win32":
            try:
                import torch
                torch.multiprocessing.freeze_support()
            except Exception:
                pass

    def setup_signal_handlers(self, cleanup_callback: Callable[[], None]) -> None:
        """Register OS-native signal handlers for graceful shutdown."""
        def _signal_handler(sig: int, frame: Any) -> None:
            logger.info("[+] Signal %d received on platform '%s'. Triggering shutdown...", sig, self.name)
            cleanup_callback()

        try:
            signal.signal(signal.SIGINT, _signal_handler)
            if hasattr(signal, "SIGTERM"):
                signal.signal(signal.SIGTERM, _signal_handler)
        except Exception as err:
            logger.warning("Could not register signal handlers on platform '%s': %s", self.name, err)

    @abstractmethod
    def audit_hardware(self) -> Dict[str, Any]:
        """Collect platform-specific hardware telemetry."""
        pass
