"""
Playback Service Implementation.

Pure index-driven playback lookup service providing exact/nearest timestamp lookup,
seek position calculation, and multi-segment stitching without filesystem scanning.
"""

from __future__ import annotations

import logging, time
from typing import Any, Optional

from camera_analytics.recording.database import MetadataDatabase
from camera_analytics.recording.schema import PlaybackSeekResult, RecordingSegment

logger = logging.getLogger(__name__)


class PlaybackService:
    """Index-Driven Playback Lookup Service."""

    def __init__(self, database: MetadataDatabase) -> None:
        self.db = database
        self._lookup_count = 0
        self._total_lookup_time_ms = 0.0

    @property
    def avg_lookup_time_ms(self) -> float:
        """Average lookup duration in milliseconds."""
        return self._total_lookup_time_ms / max(1, self._lookup_count) if self._lookup_count > 0 else 0.0

    def seek_timestamp(self, camera_id: str, timestamp: float) -> Optional[PlaybackSeekResult]:
        """Perform fast O(1) index lookup for target camera and timestamp.

        Args:
            camera_id: Camera identifier.
            timestamp: Target UTC epoch timestamp in seconds.

        Returns:
            PlaybackSeekResult instance containing target segment path and seek offset.
        """
        t0 = time.time()
        seg = self.db.find_segment_for_timestamp(camera_id, timestamp)
        latency_ms = (time.time() - t0) * 1000.0

        self._lookup_count += 1
        self._total_lookup_time_ms += latency_ms

        if not seg:
            logger.warning("PlaybackService: No recording segment found for camera '%s' at ts=%.2f", camera_id, timestamp)
            return None

        exact_match = (seg.start_timestamp <= timestamp <= seg.end_timestamp)
        seek_offset = max(0.0, timestamp - seg.start_timestamp)

        result = PlaybackSeekResult(
            camera_id=camera_id,
            requested_timestamp=timestamp,
            segment_id=seg.segment_id,
            segment_path=seg.file_path,
            seek_offset_sec=seek_offset,
            exact_match=exact_match,
            near_timestamp=seg.start_timestamp if not exact_match else timestamp,
        )

        logger.debug("PlaybackService seek result: segment='%s', seek_offset=%.2fs (latency=%.2fms)", seg.segment_id, seek_offset, latency_ms)
        return result

    def get_playlist(self, camera_id: str, start_time: float, end_time: float) -> list[RecordingSegment]:
        """Get ordered list of video segments covering a time range for multi-segment playback."""
        with self.db._lock:
            with self.db._get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT * FROM segments
                    WHERE camera_id = ? AND end_timestamp >= ? AND start_timestamp <= ?
                    ORDER BY start_timestamp ASC
                    """,
                    (camera_id, start_time, end_time),
                ).fetchall()

                playlist: list[RecordingSegment] = []
                for row in rows:
                    res_parts = str(row["resolution"]).split("x")
                    res_tuple = (int(res_parts[0]), int(res_parts[1])) if len(res_parts) == 2 else (1920, 1080)
                    playlist.append(
                        RecordingSegment(
                            segment_id=row["segment_id"],
                            camera_id=row["camera_id"],
                            file_path=row["file_path"],
                            start_timestamp=float(row["start_timestamp"]),
                            end_timestamp=float(row["end_timestamp"]),
                            duration_sec=float(row["duration_sec"]),
                            fps=float(row["fps"]),
                            resolution=res_tuple,
                            codec=row["codec"],
                            file_size_bytes=int(row["file_size_bytes"]),
                            checksum=row["checksum"],
                        )
                    )
                return playlist
