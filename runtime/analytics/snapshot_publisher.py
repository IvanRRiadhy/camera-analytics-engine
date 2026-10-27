"""
Decoupled Snapshot Publisher Component with Change Detection.

Publishes CameraAnalyticsSnapshot payloads over RabbitMQ every 2.0 seconds per camera pipeline.
Includes configurable change detection to skip publishing if plugin states are identical.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import threading
import time
from typing import Any, Dict, Optional

from camera_analytics.communication.manager import CommunicationManager
from camera_analytics.logging import RuntimeLogger
from camera_analytics.orchestration.pipeline_coordinator import PipelineCoordinator
from camera_analytics.runtime.analytics.models import CameraAnalyticsSnapshot

logger = logging.getLogger(__name__)


class SnapshotPublisher:
    """Decoupled 2-Second Periodic Camera Analytics Snapshot Publisher."""

    def __init__(
        self,
        coordinator: Optional[PipelineCoordinator] = None,
        execution_workers: Optional[list[Any]] = None,
        comm_manager: Optional[CommunicationManager] = None,
        publish_interval_sec: float = 2.0,
        enable_change_detection: bool = True,
        engine_id: str = "engine_edge_01",
    ) -> None:
        self.coordinator = coordinator
        self.execution_workers = execution_workers or []
        self.comm_manager = comm_manager
        self.publish_interval_sec = max(0.2, publish_interval_sec)
        self.enable_change_detection = enable_change_detection
        self.engine_id = engine_id

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._last_published_snapshots: Dict[str, CameraAnalyticsSnapshot] = {}

    def start(self) -> None:
        """Start 2-second background snapshot publisher loop."""
        with self._lock:
            if not self._running:
                self._running = True
                self._thread = threading.Thread(
                    target=self._publish_loop, daemon=True, name="SnapshotPublisher"
                )
                self._thread.start()
                logger.info(
                    "[SnapshotPublisher] Started Periodic Analytics Snapshot Loop (Interval: %.1fs, Change Detection: %s)",
                    self.publish_interval_sec,
                    self.enable_change_detection,
                )

    def stop(self, timeout: float = 3.0) -> None:
        """Stop background snapshot publisher loop cleanly."""
        with self._lock:
            if not self._running:
                return
            self._running = False

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
        logger.info("[SnapshotPublisher] Stopped cleanly.")

    def _publish_loop(self) -> None:
        tick_count = 0
        RuntimeLogger.forensic(
            logger,
            "[FORENSIC] _publish_loop STARTED | Thread ID: %s | Thread Name: %s | Alive: %s | Daemon: %s | Running Flag: %s",
            threading.get_ident(),
            threading.current_thread().name,
            threading.current_thread().is_alive(),
            threading.current_thread().daemon,
            self._running,
        )
        while self._running:
            tick_count += 1
            start_t = time.monotonic()
            RuntimeLogger.forensic(
                logger,
                "[FORENSIC] === Tick #%d === | Time: %s | Thread ID: %s",
                tick_count,
                datetime.now(timezone.utc).isoformat(),
                threading.get_ident(),
            )
            try:
                published = self.publish_snapshots()
                RuntimeLogger.forensic(logger, "[FORENSIC] Tick #%d Finished | Published Count: %d", tick_count, published)
            except Exception as exc:
                logger.error("[FORENSIC EXCEPTION] Exception in publish loop tick #%d: %s", tick_count, exc, exc_info=True)

            elapsed = time.monotonic() - start_t
            sleep_time = max(0.05, self.publish_interval_sec - elapsed)
            time.sleep(sleep_time)

    def _should_publish(self, camera_id: str, new_snapshot: CameraAnalyticsSnapshot) -> bool:
        if not self.enable_change_detection:
            RuntimeLogger.forensic(logger, "[FORENSIC DECISION] Camera '%s': Change detection DISABLED -> DECISION: PUBLISH", camera_id)
            return True

        last = self._last_published_snapshots.get(camera_id)
        if last is None:
            RuntimeLogger.forensic(logger, "[FORENSIC DECISION] Camera '%s': Initial snapshot (last is None) -> DECISION: PUBLISH", camera_id)
            return True

        # Check plugin state equality
        is_same = (
            last.people_counting == new_snapshot.people_counting
            and last.queue_detection == new_snapshot.queue_detection
            and last.loitering == new_snapshot.loitering
            and last.zone_occupancy == new_snapshot.zone_occupancy
            and last.health.status == new_snapshot.health.status
        )
        if is_same:
            RuntimeLogger.forensic(
                logger,
                "[FORENSIC DECISION] Camera '%s': Snapshot IS IDENTICAL to previous snapshot -> DECISION: SKIP | People: %s | Queue: %s | Loitering: %s | Health: %s",
                camera_id,
                new_snapshot.people_counting,
                new_snapshot.queue_detection,
                new_snapshot.loitering,
                new_snapshot.health.status,
            )
            return False
        else:
            RuntimeLogger.forensic(
                logger,
                "[FORENSIC DECISION] Camera '%s': Snapshot HAS CHANGED -> DECISION: PUBLISH | Prev People: %s -> New People: %s",
                camera_id,
                last.people_counting,
                new_snapshot.people_counting,
            )
            return True

    def publish_snapshots(self) -> int:
        """Publish periodic snapshots for active camera pipelines."""
        if self.coordinator is None:
            self.coordinator = PipelineCoordinator.get_instance()
        if self.comm_manager is None:
            self.comm_manager = CommunicationManager.get_instance()

        pipelines = self.coordinator.pipeline_manager.list_pipelines()
        RuntimeLogger.forensic(logger, "[FORENSIC ENGINE] Total Active Pipelines Found: %d", len(pipelines))
        if not pipelines:
            return 0

        published_count = 0

        for pipe_inst in pipelines:
            cam_id = pipe_inst.camera_id

            # Retrieve context and worker
            worker = None
            for ew in self.execution_workers:
                if str(getattr(ew, "camera_id", "")) == str(cam_id):
                    worker = ew
                    break

            aggregator = getattr(worker, "aggregator", None) or getattr(pipe_inst, "aggregator", None)

            if aggregator is None:
                logger.error(
                    "[SnapshotPublisher FATAL] Fail-Fast: No PipelineAnalyticsAggregator found for camera '%s'! Skipping snapshot build.",
                    cam_id
                )
                continue

            inf_pipe = getattr(worker, "_inference_pipeline", None) if worker else None
            ctx = getattr(inf_pipe, "last_context", getattr(pipe_inst, "last_context", None))

            snapshot = aggregator.create_snapshot(worker=worker, context=ctx)

            logger.info(
                "[FORENSIC SNAPSHOT BUILT] MsgId: %s | Cam: %s | Health FPS: %.1f | FrameCount: %d | Status: %s | People: %s | Queue: %s",
                snapshot.message_id,
                snapshot.camera_id,
                snapshot.health.fps,
                snapshot.health.frame_count,
                snapshot.health.status,
                snapshot.people_counting,
                snapshot.queue_detection,
            )

            if not self._should_publish(cam_id, snapshot):
                continue

            payload_dict = snapshot.to_dict()

            logger.info(
                "[FORENSIC RABBITMQ CALL] Invoking comm_manager.publish_raw() | Exchange: 'cctv.analytics' | RoutingKey: 'analytics.snapshot' | Payload Size: %d bytes",
                len(str(payload_dict)),
            )

            # Publish unified snapshot over RabbitMQ (analytics.snapshot topic)
            success = self.comm_manager.publish_raw(
                exchange="cctv.analytics",
                routing_key="analytics.snapshot",
                payload_dict=payload_dict,
            )

            logger.info("[FORENSIC RABBITMQ RESULT] publish_raw success: %s", success)

            if success:
                self._last_published_snapshots[cam_id] = snapshot
                published_count += 1
                logger.info(
                    "[SnapshotPublisher] Published 2s Snapshot for Camera '%s' -> FPS: %.1f, Latency: %.1fms | People: %s, Queue: %s",
                    cam_id,
                    snapshot.health.fps,
                    snapshot.health.latency_ms,
                    snapshot.people_counting.current if snapshot.people_counting else 0,
                    snapshot.queue_detection.queue_length if snapshot.queue_detection else 0,
                )

        return published_count
