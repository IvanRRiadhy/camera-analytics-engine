"""
Video Reader Component.

Coordinates VideoSource and VideoDecoder to produce immutable IngestedFrame objects
with timestamping and latency measurement.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from camera_analytics.ingestion.decoders import DecoderFactory, VideoDecoder
from camera_analytics.ingestion.models import IngestedFrame
from camera_analytics.ingestion.sources import StreamPacket, VideoSource

logger = logging.getLogger(__name__)


class VideoReader:
    """Core stream reader decoupling VideoSource I/O from VideoDecoder decoding logic."""

    def __init__(self, source: VideoSource, decoder: Optional[VideoDecoder] = None) -> None:
        self._source = source
        self._decoder = decoder or DecoderFactory.create("opencv")
        self._frame_count = 0

    @property
    def source(self) -> VideoSource:
        return self._source

    @property
    def is_open(self) -> bool:
        return self._source.is_open

    def open(self) -> bool:
        """Open underlying stream source."""
        return self._source.open()

    def read_frame(self, pipeline_id: str, camera_id: str) -> Optional[IngestedFrame]:
        """Fetch next StreamPacket, decode image, and wrap in immutable IngestedFrame.

        Args:
            pipeline_id: Target pipeline identifier string.
            camera_id: Target camera identifier string.

        Returns:
            IngestedFrame instance, or None if stream EOF/error.
        """
        start_time = time.time()
        packet = self._source.read_packet()

        if packet is None or packet.is_eof or packet.payload is None:
            return None

        try:
            image = self._decoder.decode(packet)
            height, width = image.shape[:2]
            channels = image.shape[2] if len(image.shape) == 3 else 1
            read_latency_ms = (time.time() - start_time) * 1000.0

            self._frame_count += 1
            return IngestedFrame(
                pipeline_id=pipeline_id,
                camera_id=camera_id,
                frame_number=self._frame_count,
                timestamp=packet.timestamp,
                read_latency_ms=read_latency_ms,
                image=image,
                width=width,
                height=height,
                channels=channels,
            )
        except Exception as exc:
            logger.error("VideoReader: Error decoding frame packet: %s", exc)
            return None

    def close(self) -> None:
        """Close underlying video source."""
        self._source.close()

    def reconnect(self) -> bool:
        """Close and reopen video source for connection recovery."""
        self.close()
        time.sleep(0.1)
        return self.open()
