"""
Reader Worker Component.

Per-pipeline background thread manager executing continuous video reading, frame caching in FrameBuffer,
transport queuing in FrameQueue, connection recovery backoff, and event/health monitoring.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Optional

from camera_analytics.ingestion.buffer import FrameBuffer
from camera_analytics.ingestion.hooks import IngestionEventHooks
from camera_analytics.ingestion.models import IngestionMetrics
from camera_analytics.ingestion.queue import FrameQueue
from camera_analytics.ingestion.reader import VideoReader
from camera_analytics.ingestion.states import ReaderState

logger = logging.getLogger(__name__)


class ReaderWorker:
    """Dedicated background thread worker executing video stream ingestion for a single camera pipeline."""

    def __init__(
        self,
        pipeline_id: str,
        camera_id: str,
        reader: VideoReader,
        buffer_capacity: int = 30,
        queue_capacity: int = 30,
        event_hooks: Optional[IngestionEventHooks] = None,
        max_reconnect_attempts: int = 5,
        metrics_accumulator: Optional[Any] = None,
    ) -> None:
        self._pipeline_id = pipeline_id
        self._camera_id = camera_id
        self._reader = reader
        self._buffer = FrameBuffer(capacity=buffer_capacity)
        self._queue = FrameQueue(capacity=queue_capacity)
        self._hooks = event_hooks or IngestionEventHooks()
        self._metrics = IngestionMetrics()
        self._max_reconnect_attempts = max_reconnect_attempts
        self._metrics_accumulator = metrics_accumulator

        # Observability / Clock placeholders for Sprint 11.4+
        self._clock_provider: Optional[Any] = None
        self._metrics_collector_ref: Optional[Any] = None
        self._event_bus_ref: Optional[Any] = None

        self._state = ReaderState.CREATED
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    @property
    def pipeline_id(self) -> str:
        return self._pipeline_id

    @property
    def camera_id(self) -> str:
        return self._camera_id

    @property
    def state(self) -> ReaderState:
        with self._lock:
            return self._state

    @property
    def buffer(self) -> FrameBuffer:
        return self._buffer

    @property
    def queue(self) -> FrameQueue:
        return self._queue

    @property
    def metrics(self) -> IngestionMetrics:
        with self._lock:
            return self._metrics

    @property
    def hooks(self) -> IngestionEventHooks:
        return self._hooks

    def start(self) -> bool:
        """Start the background ingestion thread."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                logger.warning("ReaderWorker[%s]: Already running.", self._pipeline_id)
                return True

            self._stop_event.clear()
            self._pause_event.clear()
            self._thread = threading.Thread(
                target=self._run_loop,
                name=f"ReaderWorker_{self._pipeline_id}",
                daemon=True,
            )
            self._thread.start()
            logger.info("ReaderWorker[%s]: Background thread started.", self._pipeline_id)
            return True

    def stop(self) -> None:
        """Stop background worker thread."""
        logger.info("ReaderWorker[%s]: Stopping background thread...", self._pipeline_id)
        self._stop_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        
        with self._lock:
            self._state = ReaderState.STOPPED
            self._reader.close()

        self._hooks.trigger_stopped(self._pipeline_id)
        logger.info("ReaderWorker[%s]: Stopped cleanly.", self._pipeline_id)

    def pause(self) -> None:
        """Pause frame ingestion loop."""
        self._pause_event.set()

    def resume(self) -> None:
        """Resume frame ingestion loop."""
        self._pause_event.clear()

    def _set_state(self, new_state: ReaderState) -> None:
        with self._lock:
            self._state = new_state

    def _run_loop(self) -> None:
        """Main execution loop running in background thread."""
        self._set_state(ReaderState.INITIALIZED)

        if not self._reader.open():
            logger.error("ReaderWorker[%s]: Failed initial stream open.", self._pipeline_id)
            self._handle_reconnect()
        else:
            self._set_state(ReaderState.READING)
            self._hooks.trigger_started(self._pipeline_id)

        last_fps_calc_time = time.time()
        fps_frame_count = 0

        while not self._stop_event.is_set():
            if self._pause_event.is_set():
                time.sleep(0.05)
                continue

            if self.state == ReaderState.RECONNECTING:
                if not self._handle_reconnect():
                    break
                continue

            frame = self._reader.read_frame(self._pipeline_id, self._camera_id)
            if frame is None:
                logger.warning("ReaderWorker[%s]: Read None frame or stream EOF.", self._pipeline_id)
                self._handle_reconnect()
                continue

            # Update Metrics & Cache Frame in FrameBuffer
            with self._lock:
                self._metrics.total_frames_read += 1
                self._metrics.last_frame_timestamp = frame.timestamp
                self._metrics.avg_read_latency_ms = frame.read_latency_ms

            pushed_clean = self._buffer.push(frame)
            if not pushed_clean:
                self._hooks.trigger_buffer_overflow(self._pipeline_id)

            # Enqueue in FrameQueue for AI Consumer
            enqueued = self._queue.put(frame, timeout=0.01)
            if not enqueued:
                with self._lock:
                    self._metrics.frame_drop_count += 1
                self._hooks.trigger_queue_full(self._pipeline_id)

            self._hooks.trigger_frame_produced(frame)

            # Calculate FPS Input Metric & Instrument Accumulator
            fps_frame_count += 1
            now = time.time()
            if now - last_fps_calc_time >= 1.0:
                calc_fps = fps_frame_count / (now - last_fps_calc_time)
                with self._lock:
                    self._metrics.fps_input = calc_fps
                if self._metrics_accumulator is not None:
                    self._metrics_accumulator.update_reader_fps(calc_fps)
                    self._metrics_accumulator.update_transport(queue_size=self._queue.size())
                fps_frame_count = 0
                last_fps_calc_time = now

        self._set_state(ReaderState.STOPPED)

    def _handle_reconnect(self) -> bool:
        """Execute connection recovery backoff sequence."""
        self._set_state(ReaderState.RECONNECTING)
        self._hooks.trigger_failed(self._pipeline_id, "Stream disconnected or read error")
        with self._lock:
            self._metrics.reconnect_count += 1

        attempts = 0
        backoff_sec = 1.0

        while not self._stop_event.is_set() and attempts < self._max_reconnect_attempts:
            attempts += 1
            logger.info("ReaderWorker[%s]: Reconnect attempt #%d in %.1fs...", self._pipeline_id, attempts, backoff_sec)
            time.sleep(backoff_sec)

            if self._reader.reconnect():
                logger.info("ReaderWorker[%s]: Reconnect SUCCESS!", self._pipeline_id)
                self._set_state(ReaderState.READING)
                self._hooks.trigger_recovered(self._pipeline_id)
                return True

            backoff_sec = min(backoff_sec * 2.0, 10.0)

        logger.error("ReaderWorker[%s]: Max reconnect attempts exceeded. State -> FAILED", self._pipeline_id)
        self._set_state(ReaderState.FAILED)
        return False
