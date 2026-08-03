"""
Segment Indexer Utility.

Calculates MD5/SHA256 checksums, resolution, file size, and duration metadata
for video segment files.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from camera_analytics.recording.schema import RecordingSegment

logger = logging.getLogger(__name__)


class SegmentIndexer:
    """Helper utility calculating segment metadata and checksums."""

    @staticmethod
    def calculate_checksum(file_path: str | Path, block_size: int = 65536) -> str:
        """Calculate MD5 checksum of a file on disk."""
        path = Path(file_path)
        if not path.exists():
            return ""

        md5 = hashlib.md5()
        try:
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(block_size), b""):
                    md5.update(chunk)
            return md5.hexdigest()
        except Exception as exc:
            logger.warning("SegmentIndexer checksum failed for '%s': %s", path, exc)
            return ""

    @classmethod
    def index_segment_file(
        cls,
        segment_id: str,
        camera_id: str,
        file_path: str | Path,
        start_timestamp: float,
        end_timestamp: float,
        fps: float = 30.0,
        resolution: tuple[int, int] = (1920, 1080),
        codec: str = "mp4v",
    ) -> RecordingSegment:
        """Construct an indexed RecordingSegment dataclass from a written file."""
        path = Path(file_path)
        file_size = path.stat().st_size if path.exists() else 0
        checksum = cls.calculate_checksum(path)
        duration = max(0.001, end_timestamp - start_timestamp)

        return RecordingSegment(
            segment_id=segment_id,
            camera_id=camera_id,
            file_path=str(path),
            start_timestamp=start_timestamp,
            end_timestamp=end_timestamp,
            duration_sec=duration,
            fps=fps,
            resolution=resolution,
            codec=codec,
            file_size_bytes=file_size,
            checksum=checksum,
        )
