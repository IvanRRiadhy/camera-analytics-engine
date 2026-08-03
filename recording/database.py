"""
SQLite Metadata Database Layer for Recording & Playback.

Stores segment metadata, event references, snapshot links, and timeline indexes.
Never duplicates video files. Fully abstracted to support future PostgreSQL migration.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from pathlib import Path
from typing import Any, Optional

from camera_analytics.recording.schema import (
    EventReference,
    RecordingSegment,
    SnapshotMetadata,
    TimelineEntry,
)

logger = logging.getLogger(__name__)


class MetadataDatabase:
    """Thread-safe SQLite Metadata Database Manager."""

    def __init__(self, db_path: str | Path = "camera_analytics/storage/metadata.db") -> None:
        self.db_path = Path(db_path).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Create sqlite3 connection with WAL mode enabled."""
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_db(self) -> None:
        """Create metadata schema and indexes."""
        with self._lock:
            with self._get_connection() as conn:
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS segments (
                        segment_id TEXT PRIMARY KEY,
                        camera_id TEXT NOT NULL,
                        file_path TEXT NOT NULL,
                        start_timestamp REAL NOT NULL,
                        end_timestamp REAL NOT NULL,
                        duration_sec REAL NOT NULL,
                        fps REAL NOT NULL,
                        resolution TEXT NOT NULL,
                        codec TEXT NOT NULL,
                        file_size_bytes INTEGER NOT NULL,
                        checksum TEXT NOT NULL
                    );

                    CREATE INDEX IF NOT EXISTS idx_segments_cam_time 
                    ON segments(camera_id, start_timestamp, end_timestamp);

                    CREATE TABLE IF NOT EXISTS event_references (
                        event_id TEXT PRIMARY KEY,
                        event_type TEXT NOT NULL,
                        camera_id TEXT NOT NULL,
                        timestamp REAL NOT NULL,
                        segment_id TEXT NOT NULL,
                        seek_offset_sec REAL NOT NULL,
                        frame_index INTEGER NOT NULL,
                        track_id INTEGER,
                        zone_id TEXT,
                        severity TEXT NOT NULL,
                        snapshot_path TEXT,
                        message TEXT NOT NULL
                    );

                    CREATE INDEX IF NOT EXISTS idx_events_cam_time 
                    ON event_references(camera_id, timestamp);

                    CREATE INDEX IF NOT EXISTS idx_events_type_time 
                    ON event_references(event_type, timestamp);

                    CREATE INDEX IF NOT EXISTS idx_events_track 
                    ON event_references(track_id);

                    CREATE TABLE IF NOT EXISTS snapshots (
                        snapshot_id TEXT PRIMARY KEY,
                        event_id TEXT NOT NULL,
                        camera_id TEXT NOT NULL,
                        timestamp REAL NOT NULL,
                        file_path TEXT NOT NULL,
                        resolution TEXT NOT NULL,
                        quality INTEGER NOT NULL
                    );

                    CREATE INDEX IF NOT EXISTS idx_snapshots_event 
                    ON snapshots(event_id);
                """)
            logger.info("MetadataDatabase initialized at '%s'", self.db_path)

    def add_segment(self, segment: RecordingSegment) -> None:
        """Insert or replace recording segment metadata."""
        with self._lock:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO segments (
                        segment_id, camera_id, file_path, start_timestamp, end_timestamp,
                        duration_sec, fps, resolution, codec, file_size_bytes, checksum
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        segment.segment_id,
                        segment.camera_id,
                        segment.file_path,
                        segment.start_timestamp,
                        segment.end_timestamp,
                        segment.duration_sec,
                        segment.fps,
                        f"{segment.resolution[0]}x{segment.resolution[1]}",
                        segment.codec,
                        segment.file_size_bytes,
                        segment.checksum,
                    ),
                )

    def find_segment_for_timestamp(self, camera_id: str, timestamp: float) -> Optional[RecordingSegment]:
        """Find video segment covering requested timestamp for camera_id."""
        with self._lock:
            with self._get_connection() as conn:
                # 1. Exact range match
                row = conn.execute(
                    """
                    SELECT * FROM segments
                    WHERE camera_id = ? AND start_timestamp <= ? AND end_timestamp >= ?
                    ORDER BY start_timestamp DESC LIMIT 1
                    """,
                    (camera_id, timestamp, timestamp),
                ).fetchone()

                if not row:
                    # 2. Nearest segment match
                    row = conn.execute(
                        """
                        SELECT *, ABS(start_timestamp - ?) AS diff FROM segments
                        WHERE camera_id = ?
                        ORDER BY diff ASC LIMIT 1
                        """,
                        (timestamp, camera_id),
                    ).fetchone()

                if row:
                    res_parts = str(row["resolution"]).split("x")
                    res_tuple = (int(res_parts[0]), int(res_parts[1])) if len(res_parts) == 2 else (1920, 1080)
                    return RecordingSegment(
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
        return None

    def add_event_reference(self, ref: EventReference) -> None:
        """Insert event reference into metadata database."""
        with self._lock:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO event_references (
                        event_id, event_type, camera_id, timestamp, segment_id,
                        seek_offset_sec, frame_index, track_id, zone_id, severity,
                        snapshot_path, message
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        ref.event_id,
                        ref.event_type,
                        ref.camera_id,
                        ref.timestamp,
                        ref.segment_id,
                        ref.seek_offset_sec,
                        ref.frame_index,
                        ref.track_id,
                        ref.zone_id,
                        ref.severity,
                        ref.snapshot_path,
                        ref.message,
                    ),
                )

    def add_snapshot(self, snap: SnapshotMetadata) -> None:
        """Insert snapshot metadata into database."""
        with self._lock:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO snapshots (
                        snapshot_id, event_id, camera_id, timestamp, file_path, resolution, quality
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        snap.snapshot_id,
                        snap.event_id,
                        snap.camera_id,
                        snap.timestamp,
                        snap.file_path,
                        f"{snap.resolution[0]}x{snap.resolution[1]}",
                        snap.quality,
                    ),
                )

    def query_events(
        self,
        camera_id: Optional[str] = None,
        event_type: Optional[str] = None,
        severity: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        track_id: Optional[int] = None,
        limit: int = 100,
    ) -> list[EventReference]:
        """Query event references matching filter conditions."""
        query = "SELECT * FROM event_references WHERE 1=1"
        params: list[Any] = []

        if camera_id:
            query += " AND camera_id = ?"
            params.append(camera_id)
        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)
        if severity:
            query += " AND severity = ?"
            params.append(severity)
        if start_time is not None:
            query += " AND timestamp >= ?"
            params.append(start_time)
        if end_time is not None:
            query += " AND timestamp <= ?"
            params.append(end_time)
        if track_id is not None:
            query += " AND track_id = ?"
            params.append(track_id)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        results: list[EventReference] = []
        with self._lock:
            with self._get_connection() as conn:
                for row in conn.execute(query, params).fetchall():
                    results.append(
                        EventReference(
                            event_id=row["event_id"],
                            event_type=row["event_type"],
                            camera_id=row["camera_id"],
                            timestamp=float(row["timestamp"]),
                            segment_id=row["segment_id"],
                            seek_offset_sec=float(row["seek_offset_sec"]),
                            frame_index=int(row["frame_index"]),
                            track_id=row["track_id"],
                            zone_id=row["zone_id"],
                            severity=row["severity"],
                            snapshot_path=row["snapshot_path"],
                            message=row["message"],
                        )
                    )
        return results

    def count_summary(self) -> dict[str, int]:
        """Return counts summary of database items."""
        with self._lock:
            with self._get_connection() as conn:
                seg_c = conn.execute("SELECT COUNT(*) FROM segments").fetchone()[0]
                evt_c = conn.execute("SELECT COUNT(*) FROM event_references").fetchone()[0]
                snp_c = conn.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]
                return {"segment_count": seg_c, "event_count": evt_c, "snapshot_count": snp_c}
