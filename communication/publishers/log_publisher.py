"""
Log File Event Publisher.

Subclass of EventPublisher that writes StandardAnalyticsEvent JSON payloads to a
JSON Lines (.jsonl) log file on disk with append mode, UTF-8 encoding, and auto-directory creation.
"""

from __future__ import annotations

import datetime
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Optional, TextIO

from camera_analytics.communication.models import (
    AnalyticsEventSerializer,
    EventDetailLevel,
    StandardAnalyticsEvent,
)
from camera_analytics.communication.publisher_base import EventPublisher
from camera_analytics.communication.registry import PublisherRegistry

logger = logging.getLogger(__name__)


@PublisherRegistry.register("log")
class LogPublisher(EventPublisher):
    """Event Publisher that logs events to a `.jsonl` (JSON Lines) file.

    Features:
        - Auto-creation of output directory.
        - Configurable detail level ('summary', 'standard', 'full').
        - Dynamic date-based filename rotation (e.g. `events_20260723.jsonl`).
        - UTF-8 encoding with append mode.
        - Thread-safe file flush.

    Args:
        name: Publisher instance identifier.
        enabled: Whether publisher is enabled.
        log_dir: Output log directory path.
        filename_pattern: Log file name pattern (supports `{date}`).
        rotate_daily: Whether to auto-rotate log files daily.
        detail_level: Configurable detail level ('summary', 'standard', 'full').
    """

    def __init__(
        self,
        name: str = "log",
        enabled: bool = True,
        log_dir: str = "logs",
        filename_pattern: str = "events_{date}.jsonl",
        rotate_daily: bool = True,
        detail_level: str = "summary",
    ) -> None:
        super().__init__(name=name, enabled=enabled)
        self._log_dir = Path(log_dir)
        self._filename_pattern = filename_pattern
        self._rotate_daily = rotate_daily
        self._detail_level = detail_level

        self._file_handle: Optional[TextIO] = None
        self._current_file_path: Optional[Path] = None
        self._current_date_str: str = ""
        self._lock = threading.Lock()

    def on_initialize(self, config: dict[str, Any]) -> None:
        """Initialize log publisher settings from config dict."""
        if "path" in config:
            path_obj = Path(config["path"])
            self._log_dir = path_obj.parent
            self._filename_pattern = path_obj.name
        elif "log_dir" in config:
            self._log_dir = Path(config["log_dir"])

        self._rotate_daily = config.get("rotate_daily", self._rotate_daily)
        self._detail_level = config.get("detail_level", self._detail_level)

    def on_start(self) -> None:
        """Create log directory and open initial log file stream."""
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._open_log_file()

    def publish(self, event: StandardAnalyticsEvent, serialized_payload: str) -> bool:
        """Write single JSON line payload to log file formatted according to detail_level.

        Args:
            event: StandardAnalyticsEvent instance.
            serialized_payload: Pre-serialized JSON string (fallback).

        Returns:
            True if written successfully, False otherwise.
        """
        if not self._is_running or not self._enabled:
            return False

        # Format payload according to configured detail level
        formatted_line = AnalyticsEventSerializer.serialize(event, detail_level=self._detail_level)

        t_start = time.time()
        with self._lock:
            try:
                # Check for daily rotation
                if self._rotate_daily:
                    today_str = datetime.date.today().strftime("%Y%m%d")
                    if today_str != self._current_date_str:
                        self._open_log_file()

                if self._file_handle is None:
                    self._open_log_file()

                if self._file_handle is not None:
                    self._file_handle.write(formatted_line + "\n")
                    latency_ms = (time.time() - t_start) * 1000.0
                    self.record_publish_metrics(success=True, latency_ms=latency_ms)
                    return True
            except Exception as exc:
                self._is_healthy = False
                logger.error("LogPublisher '%s' write error: %s", self.name, exc)
                self.record_publish_metrics(success=False, latency_ms=0.0)
                return False

        return False

    def on_flush(self) -> None:
        """Flush log file buffer to disk."""
        with self._lock:
            if self._file_handle and not self._file_handle.closed:
                try:
                    self._file_handle.flush()
                    os.fsync(self._file_handle.fileno())
                except Exception as exc:
                    logger.debug("LogPublisher '%s' flush error: %s", self.name, exc)

    def on_stop(self) -> None:
        """Flush and close log file handle."""
        with self._lock:
            if self._file_handle and not self._file_handle.closed:
                try:
                    self._file_handle.flush()
                    self._file_handle.close()
                except Exception:
                    pass
                self._file_handle = None

    # --- Internal Helpers ---

    def _open_log_file(self) -> None:
        """Determine current log file path and open file handle in append mode."""
        today_str = datetime.date.today().strftime("%Y%m%d")
        self._current_date_str = today_str

        if "{date}" in self._filename_pattern:
            filename = self._filename_pattern.replace("{date}", today_str)
        else:
            filename = self._filename_pattern

        file_path = self._log_dir / filename

        if self._file_handle is not None and not self._file_handle.closed:
            try:
                self._file_handle.flush()
                self._file_handle.close()
            except Exception:
                pass

        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._file_handle = open(file_path, mode="a", encoding="utf-8")
        self._current_file_path = file_path
        self._is_healthy = True
        logger.info("LogPublisher '%s' opened log file: %s (Detail Level: %s)", self.name, file_path, self._detail_level)
