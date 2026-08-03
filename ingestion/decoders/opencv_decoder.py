"""
OpenCV Video Decoder implementation.
"""

from __future__ import annotations

import cv2
import numpy as np

from camera_analytics.ingestion.decoders.base import DecoderFactory, VideoDecoder
from camera_analytics.ingestion.sources.base import StreamPacket


class OpenCVDecoder(VideoDecoder):
    """OpenCV implementation of VideoDecoder."""

    def decode(self, packet: StreamPacket) -> np.ndarray:
        payload = packet.payload
        if payload is None:
            raise ValueError("OpenCVDecoder: Packet payload is None.")

        if isinstance(payload, np.ndarray):
            return payload

        # Raw bytes decoding fallback
        if isinstance(payload, bytes):
            nparr = np.frombuffer(payload, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                raise ValueError("OpenCVDecoder: cv2.imdecode failed on bytes payload.")
            return img

        raise ValueError(f"OpenCVDecoder: Unsupported payload type '{type(payload)}'.")


# Register in factory
DecoderFactory.register("opencv", OpenCVDecoder)
