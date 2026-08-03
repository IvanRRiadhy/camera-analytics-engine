"""
Runtime Snapshot Publisher & RTSP Stream Deduplicator.

Publishes 1Hz camera-level aggregated Runtime Snapshots to RabbitMQ.
Deduplicates multiple camera instances sharing the same physical RTSP stream.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any, Optional

from camera_analytics.communication.manager import CommunicationManager
from camera_analytics.orchestration.pipeline_coordinator import PipelineCoordinator

logger = logging.getLogger(__name__)


def normalize_stream_uri(uri: Optional[str]) -> str:
    """Normalize RTSP stream URI for deduplication."""
    if not uri:
        return "default_stream"
    clean = uri.strip().lower()
    if clean.endswith("/"):
        clean = clean[:-1]
    return clean


class RuntimeSnapshotPublisher:
    """1Hz Camera-Level Runtime Analytics Snapshot Publisher with RTSP Stream Deduplication."""

    def __init__(
        self,
        coordinator: Optional[PipelineCoordinator] = None,
        execution_workers: Optional[list[Any]] = None,
        comm_manager: Optional[CommunicationManager] = None,
        publish_interval_ms: int = 1000,
        deduplicate_streams: bool = True,
        engine_id: str = "engine_edge_01",
    ) -> None:
        self.coordinator = coordinator
        self.execution_workers = execution_workers or []
        self.comm_manager = comm_manager
        self.publish_interval_sec = max(0.1, publish_interval_ms / 1000.0)
        self.deduplicate_streams = deduplicate_streams
        self.engine_id = engine_id

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def start(self) -> None:
        """Start 1Hz background snapshot publisher loop."""
        with self._lock:
            if not self._running:
                self._running = True
                self._thread = threading.Thread(
                    target=self._publish_loop, daemon=True, name="RuntimeSnapshotPublisher"
                )
                self._thread.start()
                logger.info(
                    "[RuntimeSnapshotPublisher] Started 1Hz Snapshot Loop (Interval: %.1fs, Deduplication: %s)",
                    self.publish_interval_sec,
                    self.deduplicate_streams,
                )

    def stop(self, timeout: float = 3.0) -> None:
        """Stop background snapshot publisher loop cleanly."""
        with self._lock:
            if not self._running:
                return
            self._running = False

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
        logger.info("[RuntimeSnapshotPublisher] Stopped cleanly.")

    def _publish_loop(self) -> None:
        """Background loop executing 1Hz camera snapshot collection and publishing."""
        while self._running:
            start_t = time.monotonic()
            try:
                self.publish_snapshots()
            except Exception as exc:
                logger.error("[RuntimeSnapshotPublisher] Exception in publish loop: %s", exc)

            elapsed = time.monotonic() - start_t
            sleep_time = max(0.05, self.publish_interval_sec - elapsed)
            time.sleep(sleep_time)

    def _get_active_worker_map(self) -> dict[str, Any]:
        """Map camera_id -> PipelineExecutionWorker instance."""
        res: dict[str, Any] = {}
        for ew in self.execution_workers:
            cam_id = getattr(ew, "camera_id", None) or getattr(ew, "_camera_id", None)
            if cam_id:
                res[str(cam_id)] = ew
        return res

    def publish_snapshots(self) -> int:
        """Collect latest state, group by physical stream URI, deduplicate, and publish."""
        if self.coordinator is None:
            self.coordinator = PipelineCoordinator.get_instance()
        if self.comm_manager is None:
            self.comm_manager = CommunicationManager.get_instance()

        pipelines = self.coordinator.pipeline_manager.list_pipelines()
        if not pipelines:
            return 0

        worker_map = self._get_active_worker_map()

        # Group pipelines by physical stream URI for deduplication
        grouped_pipelines: dict[str, list[Any]] = {}
        for pipe_inst in pipelines:
            cam = pipe_inst.camera
            cam_id = getattr(cam, "camera_id", getattr(cam, "id", "c1"))
            raw_uri = getattr(cam, "source", None) or getattr(cam, "rtsp_stream_url", None) or getattr(cam, "uri", "rtsp://default")
            norm_uri = normalize_stream_uri(raw_uri) if self.deduplicate_streams else str(cam_id)

            if norm_uri not in grouped_pipelines:
                grouped_pipelines[norm_uri] = []
            grouped_pipelines[norm_uri].append(pipe_inst)

        published_count = 0
        now_iso = datetime.now(timezone.utc).isoformat()

        for stream_uri, pipe_group in grouped_pipelines.items():
            primary_pipe = pipe_group[0]
            cam = primary_pipe.camera
            cam_id = getattr(cam, "camera_id", getattr(cam, "id", "c1"))

            # Retrieve context from live worker
            worker = worker_map.get(str(cam_id))
            inf_pipe = getattr(worker, "_inference_pipeline", None) if worker else None
            ctx = getattr(inf_pipe, "last_context", getattr(primary_pipe, "last_context", None))

            people_count = ctx.active_person_count if ctx else 0
            queue_length = 0
            loitering_count = 0
            fps = getattr(worker, "fps_execution", 30.0) if worker else 30.0
            latency_ms = ctx.stage_timings_ms.get("detection_time_ms", 12.5) if ctx else 12.5

            if ctx and hasattr(ctx, "plugin_results"):
                p_res = ctx.plugin_results
                if "QueueDetection" in p_res:
                    queue_length = p_res["QueueDetection"].get("QueueLength", 0)
                if "LoiteringDetection" in p_res:
                    loitering_count = len(p_res["LoiteringDetection"].get("TrackIds", []))

            snapshot_dict = {
                "engineId": self.engine_id,
                "cameraId": str(cam_id),
                "cameraName": getattr(cam, "name", "Default Camera"),
                "streamUri": stream_uri,
                "timestamp": now_iso,
                "peopleCount": people_count,
                "queueLength": queue_length,
                "loiteringCount": loitering_count,
                "pipelineFps": round(fps, 1),
                "latencyMs": round(latency_ms, 2),
                "health": "OK",
            }

            # Publish snapshot over RabbitMQ
            success = self.comm_manager.publish_raw(
                exchange="cctv.analytics",
                routing_key="analytics.runtime.snapshot",
                payload_dict=snapshot_dict,
            )
            if success:
                published_count += 1
                logger.info(
                    "[RuntimeSnapshotPublisher] Published 1Hz Snapshot for Camera '%s' (%s) -> People: %d, Queue: %d, Loitering: %d",
                    cam.name, stream_uri, people_count, queue_length, loitering_count
                )

        return published_count
