"""
NVIDIA Jetson ARM64 Concrete Platform Implementation for CCTV Analytics AI Engine.
"""

from __future__ import annotations

import logging
import os
import platform
import sys
from pathlib import Path
from typing import Any, Dict

from camera_analytics.platform.platform_base import RuntimePlatform

logger = logging.getLogger(__name__)


class JetsonPlatform(RuntimePlatform):
    """Concrete platform representation for NVIDIA Jetson ARM64 edge environment."""

    @property
    def name(self) -> str:
        """Return platform identifier name."""
        return "jetson"

    @property
    def target_environment(self) -> str:
        """Return target environment string."""
        return "JETSON_ARM64"

    def initialize(self) -> None:
        """Lifecycle hook: Initialize Tegra platform memory allocator and capabilities."""
        if self._is_initialized:
            return

        # Configure PyTorch allocator for Tegra unified memory safety
        os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "max_split_size_mb:64")

        self.capabilities.register_capability("opencv")
        self.capabilities.register_capability("gstreamer")
        self.capabilities.register_capability("tegrastats")
        self.capabilities.register_capability("headless_mode")

        tegra_file = Path("/etc/nv_tegra_release")
        if tegra_file.exists():
            try:
                with open(tegra_file, "r", encoding="utf-8") as f:
                    tegra_info = f.readline().strip()
                self.capabilities.set_metadata("tegra_release", tegra_info)
            except Exception:
                pass

        super().initialize()

    def audit_hardware(self) -> Dict[str, Any]:
        """Collect Jetson hardware telemetry and register capability metadata."""
        import cv2

        self.capabilities.set_metadata("os_platform", f"Jetson-Linux-{platform.release()}")
        self.capabilities.set_metadata("python_version", sys.version.split()[0])
        self.capabilities.set_metadata("opencv_version", cv2.__version__)

        info: Dict[str, Any] = {
            "platform_name": self.name,
            "target_environment": self.target_environment,
            "os_release": platform.release(),
            "python_version": sys.version.split()[0],
            "cuda_available": False,
            "gpu_name": "NVIDIA Jetson Integrated GPU",
        }
        try:
            import torch
            self.capabilities.set_metadata("pytorch_version", torch.__version__)
            if torch.cuda.is_available():
                self.capabilities.register_capability("cuda")
                self.capabilities.register_capability("pytorch_cuda")
                gpu_name = torch.cuda.get_device_name(0)
                info["cuda_available"] = True
                info["gpu_name"] = gpu_name
                self.capabilities.set_metadata("gpu_name", gpu_name)
                self.capabilities.set_metadata("cuda_version", torch.version.cuda)
        except Exception:
            pass
        return info
