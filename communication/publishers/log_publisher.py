"""
Log File Event & Telemetry Publisher with Automatic Log Rotation & Retention Quotas.

Subclass of EventPublisher that produces dual file outputs:
1. Human Readable Text Log (`logs/analytics.log`): Formatted operator report.
2. Machine Readable NDJSON Log (`logs/analytics.ndjson`): Append-only, 1 object per line, UTF-8.
   Compatible with jq, FluentBit, Elasticsearch, Loki, Grafana, Splunk.

Features size-based rotation (`max_bytes`), daily date rotation, retention policy (`keep_last_days`),
and backup quota management (`max_backup_files`).
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, TextIO

from camera_analytics.communication.models import StandardAnalyticsEvent
from camera_analytics.communication.publisher_base import EventPublisher, PublisherHealthState
from camera_analytics.communication.registry import PublisherRegistry

logger = logging.getLogger(__name__)


@PublisherRegistry.register("log")
@PublisherRegistry.register("logfile")
class LogPublisher(EventPublisher):
    """Event & Telemetry Publisher with dual human/machine output and size/date log rotation & retention."""

    def __init__(
        self,
        name: str = "log",
        enabled: bool = True,
        log_dir: str = "logs",
        human_filename: str = "analytics.log",
        ndjson_filename: str = "analytics.ndjson",
        max_bytes: int = 10 * 1024 * 1024,  # 10 MB default rotation limit
        max_backup_files: int = 5,
        keep_last_days: int = 7,
        **kwargs: Any,
    ) -> None:
        super().__init__(name=name, enabled=enabled, **kwargs)
        self._log_dir = Path(log_dir)
        self._human_filename = human_filename
        self._ndjson_filename = ndjson_filename
        self._max_bytes = max_bytes
        self._max_backup_files = max_backup_files
        self._keep_last_days = keep_last_days

        self._human_path = self._log_dir / self._human_filename
        self._ndjson_path = self._log_dir / self._ndjson_filename

        self._human_handle: Optional[TextIO] = None
        self._ndjson_handle: Optional[TextIO] = None
        self._lock = threading.Lock()

    def on_initialize(self, config: Dict[str, Any]) -> None:
        """Initialize log publisher settings from config dict."""
        if "log_dir" in config:
            self._log_dir = Path(config["log_dir"])
            self._human_path = self._log_dir / self._human_filename
            self._ndjson_path = self._log_dir / self._ndjson_filename

        self._max_bytes = config.get("max_bytes", self._max_bytes)
        self._max_backup_files = config.get("max_backup_files", config.get("backup_count", self._max_backup_files))
        self._keep_last_days = config.get("keep_last_days", self._keep_last_days)

    def on_start(self) -> None:
        """Create log directory and open persistent file streams."""
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._open_handles()

    def _open_handles(self) -> None:
        """Open persistent file handles with append mode."""
        with self._lock:
            if self._human_handle is None or self._human_handle.closed:
                self._human_handle = open(self._human_path, mode="a", encoding="utf-8")
            if self._ndjson_handle is None or self._ndjson_handle.closed:
                self._ndjson_handle = open(self._ndjson_path, mode="a", encoding="utf-8")

    def _cleanup_old_backups(self, base_path: Path) -> None:
        """Enforce retention policies (keep_last_days and max_backup_files quotas)."""
        try:
            cutoff_time = time.time() - (self._keep_last_days * 86400)
            backups = sorted(
                base_path.parent.glob(f"{base_path.name}.*"),
                key=lambda p: p.stat().st_mtime if p.exists() else 0
            )

            # 1. Purge backup files older than keep_last_days
            for b_file in backups:
                if b_file.exists() and b_file.stat().st_mtime < cutoff_time:
                    b_file.unlink(missing_ok=True)
                    logger.info("LogPublisher '%s' purged expired backup file: %s", self._name, b_file.name)

            # 2. Enforce hard max_backup_files count quota
            remaining = sorted(
                base_path.parent.glob(f"{base_path.name}.*"),
                key=lambda p: p.stat().st_mtime if p.exists() else 0
            )
            while len(remaining) > self._max_backup_files:
                oldest = remaining.pop(0)
                if oldest.exists():
                    oldest.unlink(missing_ok=True)
                    logger.info("LogPublisher '%s' purged excess backup file: %s", self._name, oldest.name)
        except Exception as exc:
            logger.warning("LogPublisher '%s' backup cleanup warning: %s", self._name, exc)

    def _check_and_rotate(self, path: Path, handle_attr: str) -> None:
        """Rotate log file if size exceeds max_bytes and enforce retention policies."""
        if not path.exists():
            return

        if path.stat().st_size >= self._max_bytes:
            handle = getattr(self, handle_attr)
            if handle and not handle.closed:
                handle.close()

            # Shift backup files (e.g. analytics.ndjson.1 -> analytics.ndjson.2)
            for i in range(self._max_backup_files - 1, 0, -1):
                s_file = path.parent / f"{path.name}.{i}"
                d_file = path.parent / f"{path.name}.{i + 1}"
                if s_file.exists():
                    if d_file.exists():
                        d_file.unlink(missing_ok=True)
                    s_file.rename(d_file)

            backup_1 = path.parent / f"{path.name}.1"
            if backup_1.exists():
                backup_1.unlink(missing_ok=True)
            path.rename(backup_1)

            # Re-open fresh file handle
            setattr(self, handle_attr, open(path, mode="a", encoding="utf-8"))

            # Run retention cleanup
            self._cleanup_old_backups(path)

    def on_publish_raw(self, exchange: str, routing_key: str, payload_dict: Dict[str, Any]) -> bool:
        """Write dual outputs: human-readable block + machine-readable NDJSON line."""
        if not self._is_running or not self._enabled:
            return False

        t_start = time.time()
        try:
            ndjson_line = json.dumps(payload_dict, separators=(",", ":"))
            human_text = self._format_human_readable(payload_dict)

            with self._lock:
                self._check_and_rotate(self._ndjson_path, "_ndjson_handle")
                self._check_and_rotate(self._human_path, "_human_handle")

                if self._ndjson_handle and not self._ndjson_handle.closed:
                    self._ndjson_handle.write(ndjson_line + "\n")
                    self._ndjson_handle.flush()

                if self._human_handle and not self._human_handle.closed:
                    self._human_handle.write(human_text + "\n")
                    self._human_handle.flush()

            latency_ms = (time.time() - t_start) * 1000.0
            self.metrics.record_success(latency_ms)
            self.set_state(PublisherHealthState.CONNECTED)
            return True
        except Exception as exc:
            logger.error("LogPublisher '%s' failed to write snapshot: %s", self._name, exc)
            self.metrics.record_failure(str(exc))
            self.set_state(PublisherHealthState.FAILED, str(exc))
            return False

    def publish(self, event: Optional[StandardAnalyticsEvent], serialized_payload: str) -> bool:
        """Publish discrete event."""
        if event is not None:
            return self.on_publish_raw("cctv.analytics", "analytics.event", event.to_dict())
        try:
            p_dict = json.loads(serialized_payload)
            return self.on_publish_raw("cctv.analytics", "analytics.event", p_dict)
        except Exception:
            return False

    def _format_human_readable(self, s: Dict[str, Any]) -> str:
        cam_id = s.get("cameraId", "Unknown")
        pipe_id = s.get("pipelineId", "Unknown")
        ts = s.get("timestamp", datetime.now(timezone.utc).isoformat())
        if "T" in ts:
            ts = ts.replace("T", " ").split(".")[0]

        health = s.get("health", {})
        fps = health.get("fps", 0.0)
        lat = health.get("latencyMs", 0.0)
        inf = health.get("inferenceTimeMs", 0.0)
        trk = health.get("trackerTimeMs", 0.0)

        plugins = s.get("plugins", {})
        pc = plugins.get("peopleCounting", {})
        qd = plugins.get("queueDetection", {})
        lo = plugins.get("loitering", {})

        pc_curr = pc.get("current", pc.get("summary", {}).get("current", 0))
        pc_ent = pc.get("entered", pc.get("summary", {}).get("entered", 0))
        pc_ext = pc.get("exited", pc.get("summary", {}).get("exited", 0))

        qd_len = qd.get("queueLength", qd.get("summary", {}).get("queueLength", 0))
        lo_act = lo.get("active", lo.get("summary", {}).get("active", 0))

        lines = [
            "---------------------------------------------------------",
            f"{ts}",
            "",
            f"Camera   : {cam_id}",
            f"Pipeline : {pipe_id}",
            "",
            "Health",
            f"  FPS       : {fps:.1f}",
            f"  Latency   : {lat:.1f} ms",
            f"  Inference : {inf:.1f} ms",
            f"  Tracker   : {trk:.1f} ms",
            "",
            "People",
            f"  Current : {pc_curr}",
            f"  Entered : {pc_ent}",
            f"  Exited  : {pc_ext}",
            "",
            "Queue",
            f"  Length  : {qd_len}",
            "",
            "Loitering",
            f"  Active  : {lo_act}",
            "---------------------------------------------------------",
        ]
        return "\n".join(lines)

    def on_stop(self) -> None:
        """Close persistent file handles cleanly."""
        with self._lock:
            if self._human_handle and not self._human_handle.closed:
                self._human_handle.close()
            if self._ndjson_handle and not self._ndjson_handle.closed:
                self._ndjson_handle.close()
