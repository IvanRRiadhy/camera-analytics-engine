"""
Video Sources package exports.
"""

from camera_analytics.ingestion.sources.base import StreamPacket, VideoSource
from camera_analytics.ingestion.sources.file_source import VideoFileSource
from camera_analytics.ingestion.sources.rtsp_source import RTSPSource
from camera_analytics.ingestion.sources.webcam_source import WebcamSource

__all__ = ["StreamPacket", "VideoSource", "RTSPSource", "VideoFileSource", "WebcamSource"]
