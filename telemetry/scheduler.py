"""
1Hz Runtime Tick Scheduler & Telemetry Pipeline.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from camera_analytics.telemetry.models import RuntimeSnapshot

logger = logging.getLogger(__name__)


class RollingFileLogger:
    """Manages structured rolling log files under logs/YYYY-MM-DD/engine_id/."""

    def __init__(self, engine_id: str = "engine_edge_01", base_dir: str = "logs") -> None:
        self.engine_id = engine_id
        self.base_dir = Path(base_dir)

    def _get_log_dir(self) -> Path:
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        log_dir = self.base_dir / today_str / self.engine_id
        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir

    def log_snapshot(self, snapshot: RuntimeSnapshot) -> None:
        """Write snapshot to rolling log files asynchronously."""
        try:
            log_dir = self._get_log_dir()
            ts = snapshot.timestamp_utc

            # 1. runtime.log
            with open(log_dir / "runtime.log", "a", encoding="utf-8") as f:
                f.write(f"[{ts}] Camera:{snapshot.camera_name} ({snapshot.camera_id}) | Pipeline:{snapshot.pipeline_id} | FPS:{snapshot.fps} | Latency:{snapshot.processing_latency_ms}ms | Detections:{snapshot.detection_count} | Tracks:{snapshot.track_count}\n")

            # 2. plugins.log
            with open(log_dir / "plugins.log", "a", encoding="utf-8") as f:
                f.write(f"[{ts}] PluginsState: {snapshot.plugin_results}\n")

            # 3. performance.log
            with open(log_dir / "performance.log", "a", encoding="utf-8") as f:
                f.write(f"[{ts}] GPU:{snapshot.gpu_utilization}% | CPU:{snapshot.cpu_utilization}% | RAM:{snapshot.ram_utilization}%\n")

        except Exception as exc:
            logger.error("[RollingFileLogger] Exception writing rolling log files: %s", exc)


class RuntimeTickScheduler:
    """1Hz Runtime Tick Scheduler publishing RuntimeSnapshot every second."""

    def __init__(self, pipeline_id: str = "pipeline_cam_lobby_01", camera_name: str = "CAM-01 Main Lobby", publisher: Any = None) -> None:
        self.pipeline_id = pipeline_id
        self.camera_name = camera_name
        self.publisher = publisher

        self.file_logger = RollingFileLogger()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._frame_count = 0

    def start(self) -> None:
        """Start 1Hz background tick loop."""
        if not self._running:
            self._running = True
            self._thread = threading.Thread(target=self._tick_loop, daemon=True, name="RuntimeTickScheduler")
            self._thread.start()
            logger.info("[RuntimeTickScheduler] Started 1Hz Runtime Tick loop for pipeline '%s'.", self.pipeline_id)

    def stop(self) -> None:
        """Stop background tick loop."""
        self._running = False

    def _tick_loop(self) -> None:
        while self._running:
            start_t = time.perf_counter()
            self._frame_count += 30

            snapshot = RuntimeSnapshot(
                camera_name=self.camera_name,
                pipeline_id=self.pipeline_id,
                frame_index=self._frame_count,
            )

            # 1. Print Structured Console Output
            self._print_console_output(snapshot)

            # 2. Log to Rolling Files
            self.file_logger.log_snapshot(snapshot)

            # 3. Publish over RabbitMQ topic (analytics/runtime/tick)
            if self.publisher:
                try:
                    self.publisher.publish(snapshot.to_json(), routing_key="runtime.tick.engine_edge_01")
                except Exception as exc:
                    logger.debug("[RuntimeTickScheduler] RabbitMQ publish notice: %s", exc)

            elapsed = time.perf_counter() - start_t
            sleep_time = max(0.0, 1.0 - elapsed)
            time.sleep(sleep_time)

    def _print_console_output(self, snapshot: RuntimeSnapshot) -> None:
        now_time = datetime.now().strftime("%H:%M:%S")
        lines = [
            "-------------------------------------------------------",
            f"[{now_time}]",
            f"Camera : {snapshot.camera_name}",
            f"Pipeline : {snapshot.pipeline_id}",
            f"FPS : {int(snapshot.fps)}",
            f"Latency : {snapshot.processing_latency_ms}ms",
            f"Detection : {snapshot.detection_count}",
            f"Tracks : {snapshot.track_count}",
            f"Events : {snapshot.published_events}",
            "Plugins",
            f"  People Counting : In={snapshot.plugin_results['PeopleCounting']['CountIn']} Out={snapshot.plugin_results['PeopleCounting']['CountOut']} Occupancy={snapshot.plugin_results['PeopleCounting']['Occupancy']}",
            f"  Queue Detection : {'TRUE' if snapshot.plugin_results['QueueDetection']['QueueDetected'] else 'FALSE'}",
            f"  Loitering : {'TRUE' if snapshot.plugin_results['LoiteringDetection']['Detected'] else 'FALSE'}",
            "-------------------------------------------------------"
        ]
        print("\n".join(lines), flush=True)
