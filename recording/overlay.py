"""
Enterprise Debug Visualization Overlay.

Renders per-track active event badges (Event Type, Track ID, Zone, Module, Severity, Event ID, Duration)
and an optional chronological event timeline ticker directly onto debug video frames using OpenCV.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import cv2
import numpy as np

from camera_analytics.communication.models import StandardAnalyticsEvent

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class DebugOverlayConfig:
    """Configuration options for Debug Visualization Overlay.

    Attributes:
        enabled: Whether debug overlay is active.
        show_track_badges: Render per-track event badges over bounding boxes.
        show_timeline_banner: Render chronological event ticker at bottom of frame.
        badge_font_scale: Font scaling factor for text labels.
        banner_height_px: Height of bottom timeline ticker banner in pixels.
        max_ticker_events: Maximum number of recent events displayed on bottom banner.
    """

    enabled: bool = True
    show_track_badges: bool = True
    show_timeline_banner: bool = True
    badge_font_scale: float = 0.45
    banner_height_px: int = 40
    max_ticker_events: int = 4


class DebugVisualizationOverlay:
    """OpenCV Overlay Engine rendering debug analytics badges and timeline banner onto frames."""

    SEVERITY_COLORS = {
        "CRITICAL": (0, 0, 255),      # Bright Red (BGR)
        "ALERT": (0, 69, 255),        # Red-Orange
        "WARNING": (0, 215, 255),     # Yellow-Gold
        "INFO": (255, 191, 0),        # Cyan-Blue
    }

    def __init__(self, config: Optional[DebugOverlayConfig] = None) -> None:
        self.config = config or DebugOverlayConfig()
        self._active_track_events: dict[int, list[dict[str, Any]]] = {}
        self._timeline_ticker: list[dict[str, Any]] = []

    def register_event(
        self,
        event: StandardAnalyticsEvent,
        bbox: Optional[list[int]] = None,
        duration_sec: float = 0.0,
    ) -> None:
        """Register an active analytics event for overlay rendering.

        Args:
            event: StandardAnalyticsEvent instance.
            bbox: Optional bounding box [x1, y1, x2, y2].
            duration_sec: Event duration in seconds (for loitering/dwell).
        """
        if not self.config.enabled:
            return

        ts_str = event.timestamp.split("T")[-1][:8] if "T" in event.timestamp else event.timestamp

        event_data = {
            "event_id": event.event_id[:8],
            "event_type": event.event_type,
            "analytics_module": event.analytics_module,
            "severity": event.severity,
            "zone_name": event.zone_name or event.zone_id or "N/A",
            "track_id": event.track_id,
            "duration_sec": duration_sec,
            "bbox": bbox,
            "timestamp_str": ts_str,
            "added_time": time.time(),
        }

        # Add to track-specific event stack if track_id exists
        if event.track_id is not None:
            if event.track_id not in self._active_track_events:
                self._active_track_events[event.track_id] = []
            # Replace existing event of same type for track or append
            existing = [e for e in self._active_track_events[event.track_id] if e["event_type"] == event.event_type]
            if not existing:
                self._active_track_events[event.track_id].append(event_data)
            else:
                existing[0].update(event_data)

        # Add to timeline ticker list
        self._timeline_ticker.append(event_data)
        if len(self._timeline_ticker) > self.config.max_ticker_events:
            self._timeline_ticker.pop(0)

    def draw_overlay(
        self,
        frame: np.ndarray,
        track_bboxes: Optional[dict[int, list[int]]] = None,
    ) -> np.ndarray:
        """Draw event badges and timeline ticker onto frame image copy.

        Args:
            frame: Input BGR numpy frame image.
            track_bboxes: Optional dictionary mapping track_id -> [x1, y1, x2, y2].

        Returns:
            Overlayed numpy image frame.
        """
        if not self.config.enabled or frame is None or frame.size == 0:
            return frame

        canvas = frame.copy()
        h_frame, w_frame = canvas.shape[:2]

        # 1. Draw Per-Track Event Badges
        if self.config.show_track_badges and (self._active_track_events or track_bboxes):
            self._draw_track_badges(canvas, track_bboxes or {})

        # 2. Draw Bottom Timeline Banner
        if self.config.show_timeline_banner and self._timeline_ticker:
            self._draw_timeline_banner(canvas, h_frame, w_frame)

        return canvas

    def _draw_track_badges(
        self,
        canvas: np.ndarray,
        track_bboxes: dict[int, list[int]],
    ) -> None:
        """Render stacked event badges over track bounding boxes."""
        font = cv2.FONT_HERSHEY_SIMPLEX
        scale = self.config.badge_font_scale

        for track_id, events in list(self._active_track_events.items()):
            if not events:
                continue

            # Find target position for badge stack
            bbox = track_bboxes.get(track_id)
            if not bbox and events[0].get("bbox"):
                bbox = events[0]["bbox"]

            if bbox and len(bbox) == 4:
                x1, y1, x2, y2 = bbox
            else:
                x1, y1 = 50, 50

            stack_offset_y = y1 - 10

            # Draw each stacked event badge
            for evt in events:
                sev = evt.get("severity", "INFO")
                color = self.SEVERITY_COLORS.get(sev, (255, 191, 0))

                dur_str = f" ({evt['duration_sec']:.1f}s)" if evt.get("duration_sec", 0) > 0 else ""
                label = f"[{evt['event_type']}] #{track_id} | Z:{evt['zone_name']}{dur_str}"

                (t_w, t_h), _ = cv2.getTextSize(label, font, scale, 1)

                bx1 = max(0, x1)
                by1 = max(0, stack_offset_y - t_h - 6)
                bx2 = min(canvas.shape[1], bx1 + t_w + 10)
                by2 = max(0, stack_offset_y)

                # Draw filled background badge & border
                cv2.rectangle(canvas, (bx1, by1), (bx2, by2), (20, 20, 20), cv2.FILLED)
                cv2.rectangle(canvas, (bx1, by1), (bx2, by2), color, 1)
                cv2.putText(canvas, label, (bx1 + 5, by2 - 4), font, scale, color, 1, cv2.LINE_AA)

                stack_offset_y -= (t_h + 8)

    def _draw_timeline_banner(
        self,
        canvas: np.ndarray,
        h_frame: int,
        w_frame: int,
    ) -> None:
        """Render semi-transparent bottom banner ticker showing recent events."""
        banner_h = self.config.banner_height_px
        banner_y1 = max(0, h_frame - banner_h)

        overlay = canvas.copy()
        cv2.rectangle(overlay, (0, banner_y1), (w_frame, h_frame), (15, 15, 15), cv2.FILLED)
        cv2.addWeighted(overlay, 0.75, canvas, 0.25, 0, canvas)

        cv2.line(canvas, (0, banner_y1), (w_frame, banner_y1), (0, 215, 255), 1)

        font = cv2.FONT_HERSHEY_SIMPLEX
        scale = 0.4

        # Render recent event ticker items horizontally
        x_cursor = 10
        for evt in self._timeline_ticker[-self.config.max_ticker_events :]:
            sev = evt.get("severity", "INFO")
            color = self.SEVERITY_COLORS.get(sev, (255, 191, 0))

            text = f"[{evt['timestamp_str']}] {evt['event_type']} ({evt['analytics_module']})"
            (t_w, t_h), _ = cv2.getTextSize(text, font, scale, 1)

            if x_cursor + t_w + 15 > w_frame:
                break

            cv2.putText(canvas, text, (x_cursor, banner_y1 + 25), font, scale, color, 1, cv2.LINE_AA)
            x_cursor += t_w + 20
