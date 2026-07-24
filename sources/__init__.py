"""
Frame sources package.

Exports the abstract FrameSource port and data structures along with
concrete source implementations:
    - FrameSource, SourceMetadata, FramePacket
    - VideoSource, RTSPSource, USBCameraSource, FolderSource
"""

from camera_analytics.sources.base import FramePacket, FrameSource, SourceMetadata
from camera_analytics.sources.folder_source import FolderSource
from camera_analytics.sources.rtsp_source import RTSPSource
from camera_analytics.sources.usb_source import USBCameraSource
from camera_analytics.sources.video_source import VideoSource

__all__ = [
    # Base Contracts & Data Structures
    "FrameSource",
    "SourceMetadata",
    "FramePacket",
    # Concrete Sources
    "VideoSource",
    "RTSPSource",
    "USBCameraSource",
    "FolderSource",
]
