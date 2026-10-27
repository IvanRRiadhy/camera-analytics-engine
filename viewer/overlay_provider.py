"""
Generic Runtime Debug Overlay Provider (Sprint H1.5B).

Provides model-agnostic RuntimeDebugInfo containers and RuntimeOverlayProvider for the Standalone Viewer.
Decouples OverlayRenderer from AI model implementations, supporting multi-module multi-track telemetry,
status tracking, skip reason diagnostics, AI Capability matching, and automatic TTL expiration purging.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

logger = logging.getLogger(__name__)


@dataclass
class RuntimeDebugInfo:
    """Generic AI Debug DTO passed to Standalone OverlayRenderer.

    Supports all present and future AI modules (Age, Gender, Emotion, PPE, ReID, Gesture, OCR).
    """

    track_id: int
    module_id: str
    capabilities: tuple[str, ...] = ("Age", "Gender")
    attributes: dict[str, Any] = field(default_factory=dict)
    raw_outputs: dict[str, Any] = field(default_factory=dict)
    status: str = "EXECUTED"                # "RUNNING" | "EXECUTED" | "SKIPPED" | "FAILED"
    skip_reason: Optional[str] = None       # "Low Face Quality" | "Low Visibility" | "Cooldown Active" | "Frame Stride"
    face_quality: float = 0.0
    latency_ms: float = 0.0
    timestamp_utc: float = field(default_factory=time.time)
    ttl_seconds: float = 2.0

    @property
    def is_expired(self) -> bool:
        """Return True if entry has exceeded its time-to-live (TTL)."""
        return (time.time() - self.timestamp_utc) > self.ttl_seconds


class RuntimeOverlayProvider:
    """Centralized manager storing active RuntimeDebugInfo snapshots for the Standalone Viewer."""

    def __init__(self, default_ttl_seconds: float = 2.0) -> None:
        self.default_ttl_seconds = default_ttl_seconds
        # Structure: camera_id -> track_id -> module_id -> RuntimeDebugInfo
        self._store: dict[str, dict[int, dict[str, RuntimeDebugInfo]]] = {}

    def update_debug_info(self, camera_id: str, info: RuntimeDebugInfo) -> None:
        """Register or update a RuntimeDebugInfo entry."""
        if camera_id not in self._store:
            self._store[camera_id] = {}
        if info.track_id not in self._store[camera_id]:
            self._store[camera_id][info.track_id] = {}

        self._store[camera_id][info.track_id][info.module_id] = info

    def get_track_debug_info(self, camera_id: str, track_id: int) -> list[RuntimeDebugInfo]:
        """Return active, non-expired debug entries for a specific track."""
        self._purge_expired(camera_id)
        cam_data = self._store.get(camera_id, {})
        track_data = cam_data.get(track_id, {})
        return [info for info in track_data.values() if not info.is_expired]

    def get_all_camera_debug_info(self, camera_id: str) -> dict[int, list[RuntimeDebugInfo]]:
        """Return all active non-expired debug entries grouped by track_id for a camera."""
        self._purge_expired(camera_id)
        cam_data = self._store.get(camera_id, {})
        res: dict[int, list[RuntimeDebugInfo]] = {}
        for t_id, modules in cam_data.items():
            valid_infos = [info for info in modules.values() if not info.is_expired]
            if valid_infos:
                res[t_id] = valid_infos
        return res

    def _purge_expired(self, camera_id: str) -> None:
        """Purge debug entries exceeding their TTL."""
        if camera_id not in self._store:
            return
        
        expired_tracks = []
        for t_id, modules in self._store[camera_id].items():
            expired_mods = [m_id for m_id, info in modules.items() if info.is_expired]
            for m_id in expired_mods:
                del modules[m_id]
            if not modules:
                expired_tracks.append(t_id)

        for t_id in expired_tracks:
            del self._store[camera_id][t_id]

    def clear(self, camera_id: Optional[str] = None) -> None:
        """Clear overlay provider data."""
        if camera_id:
            self._store.pop(camera_id, None)
        else:
            self._store.clear()
