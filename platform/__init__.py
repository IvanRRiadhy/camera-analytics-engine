"""
CCTV Analytics AI Engine Platform Abstraction Package.
"""

from camera_analytics.platform.docker_platform import DockerPlatform
from camera_analytics.platform.factory import PlatformFactory
from camera_analytics.platform.jetson_platform import JetsonPlatform
from camera_analytics.platform.linux_platform import LinuxPlatform
from camera_analytics.platform.platform_base import RuntimePlatform
from camera_analytics.platform.windows_platform import WindowsPlatform

__all__ = [
    "RuntimePlatform",
    "PlatformFactory",
    "WindowsPlatform",
    "LinuxPlatform",
    "JetsonPlatform",
    "DockerPlatform",
]
