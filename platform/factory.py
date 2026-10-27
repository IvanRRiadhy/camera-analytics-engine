"""
Dynamic PlatformFactory Class Registry for CCTV Analytics AI Engine.

Uses extensible class registry (cls.register_platform(env_code, platform_cls))
enabling seamless registration of new edge targets (JETSON_ORIN, RASPBERRY_PI_AI, OPENVINO_APPLIANCE).
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Dict, Optional, Type

from camera_analytics.platform.docker_platform import DockerPlatform
from camera_analytics.platform.jetson_platform import JetsonPlatform
from camera_analytics.platform.linux_platform import LinuxPlatform
from camera_analytics.platform.platform_base import RuntimePlatform
from camera_analytics.platform.windows_platform import WindowsPlatform

logger = logging.getLogger(__name__)


class PlatformFactory:
    """Factory managing dynamic registration and instantiation of RuntimePlatform classes."""

    _instance: Optional[RuntimePlatform] = None
    _registry: Dict[str, Type[RuntimePlatform]] = {}

    @classmethod
    def register_platform(cls, env_code: str, platform_cls: Type[RuntimePlatform]) -> None:
        """Register a new platform class into the factory registry.

        Args:
            env_code: Target environment identifier (e.g. 'WIN_X64', 'JETSON_ORIN').
            platform_cls: Concrete RuntimePlatform class reference.
        """
        code = env_code.upper()
        cls._registry[code] = platform_cls
        logger.info("[+] Platform Registered: '%s' -> %s", code, platform_cls.__name__)

    @classmethod
    def _ensure_default_registry(cls) -> None:
        """Initialize built-in platform classes if not registered."""
        if "WIN_X64" not in cls._registry:
            cls.register_platform("WIN_X64", WindowsPlatform)
        if "LINUX_X64" not in cls._registry:
            cls.register_platform("LINUX_X64", LinuxPlatform)
        if "JETSON_ARM64" not in cls._registry:
            cls.register_platform("JETSON_ARM64", JetsonPlatform)
        if "JETSON_NANO" not in cls._registry:
            cls.register_platform("JETSON_NANO", JetsonPlatform)
        if "JETSON_XAVIER" not in cls._registry:
            cls.register_platform("JETSON_XAVIER", JetsonPlatform)
        if "JETSON_ORIN" not in cls._registry:
            cls.register_platform("JETSON_ORIN", JetsonPlatform)
        if "DOCKER_CONTAINER" not in cls._registry:
            cls.register_platform("DOCKER_CONTAINER", DockerPlatform)

    @classmethod
    def create_platform(cls, force_env: Optional[str] = None) -> RuntimePlatform:
        """Create or return active RuntimePlatform singleton."""
        if cls._instance is not None and force_env is None:
            return cls._instance

        cls._ensure_default_registry()
        env_code = (force_env or cls.detect_environment()).upper()

        platform_cls = cls._registry.get(env_code, WindowsPlatform)
        platform_obj = platform_cls()

        if force_env is None:
            cls._instance = platform_obj

        logger.info("[+] Platform Created via Registry: '%s' (%s)", platform_obj.name, platform_obj.target_environment)
        return platform_obj

    @classmethod
    def detect_environment(cls) -> str:
        """Detect environment from OS, device files, and environment variables."""
        if Path("/.dockerenv").exists() or os.environ.get("DOCKER_CONTAINER") == "1":
            return "DOCKER_CONTAINER"
        if Path("/etc/nv_tegra_release").exists() or Path("/usr/bin/tegrastats").exists():
            return "JETSON_ARM64"
        if sys.platform.startswith("linux"):
            return "LINUX_X64"
        return "WIN_X64"
