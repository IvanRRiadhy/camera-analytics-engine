"""
Windows x64 Concrete Platform Implementation for CCTV Analytics AI Engine.
"""

from __future__ import annotations

import logging
import platform
import sys
from typing import Any, Dict

from camera_analytics.platform.platform_base import RuntimePlatform

logger = logging.getLogger(__name__)


class WindowsPlatform(RuntimePlatform):
    """Concrete platform representation for Windows x64 environment."""

    @property
    def name(self) -> str:
        """Return platform identifier name."""
        return "windows"

    @property
    def target_environment(self) -> str:
        """Return target environment string."""
        return "WIN_X64"

    def audit_hardware(self) -> Dict[str, Any]:
        """Collect Windows hardware telemetry and register capability metadata."""
        import cv2

        self.capabilities.register_capability("opencv")
        self.capabilities.register_capability("studio_gui")
        self.capabilities.register_capability("viewer")
        self.capabilities.set_metadata("os_platform", f"Windows-{platform.release()}")
        self.capabilities.set_metadata("python_version", sys.version.split()[0])
        self.capabilities.set_metadata("opencv_version", cv2.__version__)

        info: Dict[str, Any] = {
            "platform_name": self.name,
            "target_environment": self.target_environment,
            "os_release": platform.release(),
            "python_version": sys.version.split()[0],
            "cuda_available": False,
            "gpu_name": "N/A",
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
