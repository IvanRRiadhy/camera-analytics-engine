"""
Video Segment Recorder Implementation.

Engine capable of continuously recording video frames into rotated segment files
using OpenCV `cv2.VideoWriter`. Guarantees zero frame loss during file rotation and
indexes segments into `MetadataDatabase`.
"""

from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Optional

import cv2
import numpy as np

from camera_analytics.recording.database import MetadataDatabase
from camera_analytics.recording.schema import RecordingSegment
from camera_analytics.recording.segment_index import SegmentIndexer
from camera_analytics.recording.storage_backend import LocalStorageBackend, StorageBackend

from camera_analytics.recording.overlay import DebugVisualizationOverlay

logger = logging.getLogger(__name__)


class VideoSegmentRecorder:
    """Continuous video recorder managing segment rotation and database indexing."""

    def __init__(
        self,
        camera_id: str = "default_cam",
        segment_duration_sec: float = 60.0,
        fps: float = 30.0,
        resolution: tuple[int, int] = (1920, 1080),
        fourcc: str = "mp4v",
        storage_backend: Optional[StorageBackend] = None,
        database: Optional[MetadataDatabase] = None,
        debug_overlay: Optional[DebugVisualizationOverlay] = None,
    ) -> None:
        self.camera_id = camera_id
        self.segment_duration_sec = segment_duration_sec
        self.fps = fps
        self.resolution = resolution
        self.fourcc_str = fourcc
        self.storage = storage_backend or LocalStorageBackend()
        self.db = database or MetadataDatabase()
        self.debug_overlay = debug_overlay

        self._writer: Optional[cv2.VideoWriter] = None
        self._current_segment_id: str = ""
        self._current_file_path: Optional[Path] = None
        self._segment_start_ts: float = 0.0
        self._last_frame_ts: float = 0.0
        self._frames_written: int = 0
        self._dropped_frames: int = 0
        self._lock = threading.Lock()
        self._is_active = False

    @property
    def is_active(self) -> bool:
        """Whether recorder is actively recording."""
        return self._is_active

    @property
    def current_segment_id(self) -> str:
        """ID of currently active recording segment."""
        return self._current_segment_id

    def start(self) -> None:
        """Start the recorder session."""
        with self._lock:
            if self._is_active:
                return
            self._is_active = True
            self._open_new_segment(time.time())
            logger.info("VideoSegmentRecorder started for camera '%s'", self.camera_id)

    def write_frame(
        self,
        frame: np.ndarray,
        timestamp: Optional[float] = None,
        track_bboxes: Optional[dict[int, list[int]]] = None,
    ) -> bool:
        """Write a video frame image into active segment file. Auto-rotates segment when duration expires.

        Args:
            frame: BGR image numpy array.
            timestamp: Frame timestamp (defaults to current epoch time).
            track_bboxes: Optional dict mapping track_id -> [x1, y1, x2, y2].

        Returns:
            True if written successfully, False otherwise.
        """
        if not self._is_active or frame is None or frame.size == 0:
            return False

        ts = timestamp if timestamp is not None else time.time()

        with self._lock:
            # Check if segment rotation is needed
            if (ts - self._segment_start_ts) >= self.segment_duration_sec:
                self._rotate_segment(ts)

            if self._writer is None:
                self._open_new_segment(ts)

            # Apply debug visualization overlay if enabled
            if self.debug_overlay is not None and self.debug_overlay.config.enabled:
                frame = self.debug_overlay.draw_overlay(frame, track_bboxes=track_bboxes)

            # Ensure resolution matches writer
            h, w = frame.shape[:2]
            if (w, h) != self.resolution:
                frame = cv2.resize(frame, self.resolution)

            try:
                self._writer.write(frame)
                self._frames_written += 1
                self._last_frame_ts = ts
                return True
            except Exception as exc:
                self._dropped_frames += 1
                logger.error("VideoSegmentRecorder write error for '%s': %s", self.camera_id, exc)
                return False

    def _open_new_segment(self, timestamp: float) -> None:
        """Open a new segment VideoWriter."""
        self._current_segment_id = f"seg_{self.camera_id}_{int(timestamp)}_{str(uuid.uuid4())[:6]}"
        self._segment_start_ts = timestamp
        self._current_file_path = self.storage.get_segment_path(
            self.camera_id, self._current_segment_id, timestamp
        )

        fourcc = cv2.VideoWriter_fourcc(*self.fourcc_str)
        self._writer = cv2.VideoWriter(
            str(self._current_file_path),
            fourcc,
            self.fps,
            self.resolution,
        )
        logger.debug(
            "VideoSegmentRecorder opened segment '%s' -> %s",
            self._current_segment_id,
            self._current_file_path,
        )

    def _rotate_segment(self, current_timestamp: float) -> None:
        """Close current segment and index it into MetadataDatabase, then open new segment."""
        if self._writer is not None:
            self._writer.release()
            self._writer = None

            if self._current_file_path and self._current_file_path.exists():
                seg = SegmentIndexer.index_segment_file(
                    segment_id=self._current_segment_id,
                    camera_id=self.camera_id,
                    file_path=self._current_file_path,
                    start_timestamp=self._segment_start_ts,
                    end_timestamp=current_timestamp,
                    fps=self.fps,
                    resolution=self.resolution,
                    codec=self.fourcc_str,
                )
                self.db.add_segment(seg)

        self._open_new_segment(current_timestamp)

    def stop(self) -> None:
        """Stop recorder and close current active segment."""
        with self._lock:
            if not self._is_active:
                return
            if self._writer is not None:
                self._writer.release()
                self._writer = None

                end_ts = self._last_frame_ts if self._last_frame_ts > 0 else time.time()
                if self._current_file_path and self._current_file_path.exists():
                    seg = SegmentIndexer.index_segment_file(
                        segment_id=self._current_segment_id,
                        camera_id=self.camera_id,
                        file_path=self._current_file_path,
                        start_timestamp=self._segment_start_ts,
                        end_timestamp=end_ts,
                        fps=self.fps,
                        resolution=self.resolution,
                        codec=self.fourcc_str,
                    )
                    self.db.add_segment(seg)

            self._is_active = False
            logger.info("VideoSegmentRecorder stopped for camera '%s'", self.camera_id)
