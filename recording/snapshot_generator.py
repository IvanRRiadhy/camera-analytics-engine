"""
Snapshot Generator Implementation.

Automatically crops and saves JPEG snapshot images on disk for configurable alert event types
(e.g. `CROWD_ALERT`, `LOITERING`, `DIRECTION_VIOLATION`, `ZONE_ENTER`, `ZONE_EXIT`, `QUEUE_ALERT`)
and links snapshot metadata in `MetadataDatabase`.
"""

from __future__ import annotations

import logging
import time
import uuid
from pathlib import Path
from typing import Any, Optional

import cv2
import numpy as np

from camera_analytics.communication.models import StandardAnalyticsEvent
from camera_analytics.recording.database import MetadataDatabase
from camera_analytics.recording.schema import SnapshotMetadata
from camera_analytics.recording.storage_backend import LocalStorageBackend, StorageBackend

logger = logging.getLogger(__name__)


class SnapshotGenerator:
    """JPEG Snapshot Generator for alert events."""

    def __init__(
        self,
        storage_backend: Optional[StorageBackend] = None,
        database: Optional[MetadataDatabase] = None,
        quality: int = 90,
        trigger_event_types: Optional[list[str]] = None,
    ) -> None:
        self.storage = storage_backend or LocalStorageBackend()
        self.db = database or MetadataDatabase()
        self.quality = max(10, min(100, quality))
        self.trigger_event_types = set(
            trigger_event_types
            or [
                "CROWD_ALERT",
                "LOITERING",
                "DIRECTION_VIOLATION",
                "ZONE_ENTER",
                "ZONE_EXIT",
                "QUEUE_ALERT",
            ]
        )

    def generate_snapshot(
        self,
        event: StandardAnalyticsEvent,
        frame: Optional[np.ndarray],
    ) -> Optional[SnapshotMetadata]:
        """Generate and save JPEG snapshot for event if event_type is in trigger list.

        Args:
            event: StandardAnalyticsEvent dataclass instance.
            frame: Optional BGR frame image numpy array.

        Returns:
            SnapshotMetadata instance if created, None otherwise.
        """
        if frame is None or frame.size == 0:
            return None

        if "*" not in self.trigger_event_types and event.event_type not in self.trigger_event_types:
            return None

        snapshot_id = f"snap_{event.event_id[:8]}_{int(time.time())}"
        target_path = self.storage.get_snapshot_path(event.camera_id, snapshot_id, time.time())

        h, w = frame.shape[:2]

        try:
            encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), self.quality]
            success, encoded_img = cv2.imencode(".jpg", frame, encode_params)
            if not success:
                logger.warning("SnapshotGenerator encoding failed for event '%s'", event.event_id)
                return None

            with open(target_path, "wb") as f:
                f.write(encoded_img.tobytes())

            snap_meta = SnapshotMetadata(
                snapshot_id=snapshot_id,
                event_id=event.event_id,
                camera_id=event.camera_id,
                timestamp=time.time(),
                file_path=str(target_path),
                resolution=(w, h),
                quality=self.quality,
            )

            self.db.add_snapshot(snap_meta)
            logger.debug("SnapshotGenerator saved JPEG snapshot: %s", target_path)
            return snap_meta

        except Exception as exc:
            logger.error("SnapshotGenerator failed to write snapshot for event '%s': %s", event.event_id, exc)
            return None
