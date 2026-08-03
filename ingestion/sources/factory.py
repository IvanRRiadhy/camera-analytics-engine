"""
Video Source Factory implementation.

Automatically selects and instantiates the correct VideoSource implementation (RTSPSource, VideoFileSource, etc.)
based on the provided stream URI prefix and type.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from camera_analytics.ingestion.sources.base import VideoSource
from camera_analytics.ingestion.sources.file_source import VideoFileSource
from camera_analytics.ingestion.sources.rtsp_source import RTSPSource

logger = logging.getLogger(__name__)


def create_video_source(uri: str, params: Optional[dict[str, Any]] = None) -> VideoSource:
    """Instantiate appropriate VideoSource subclass based on URI scheme.

    Rules:
        - 'rtsp://' or 'rtsps://' -> RTSPSource
        - 'http://' or 'https://' -> RTSPSource (HTTP video stream / MJPEG)
        - Files (.mp4, .avi, .mkv, .sdp file paths) -> VideoFileSource

    Args:
        uri: Resource URI string.
        params: Optional configuration parameters dictionary.

    Returns:
        Instantiated VideoSource.
    """
    uri_clean = str(uri).strip()

    if uri_clean.lower().startswith(("rtsp://", "rtsps://")):
        logger.info("SourceFactory: Selected RTSPSource for URI '%s'", uri_clean)
        return RTSPSource(uri=uri_clean, params=params)

    if uri_clean.lower().startswith(("http://", "https://")):
        logger.info("SourceFactory: Selected RTSPSource (HTTP/MJPEG) for URI '%s'", uri_clean)
        return RTSPSource(uri=uri_clean, params=params)

    logger.info("SourceFactory: Selected VideoFileSource for URI '%s'", uri_clean)
    return VideoFileSource(file_path=uri_clean, params=params)
