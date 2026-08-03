"""
Pipeline Execution Worker Component.

Dedicated background thread worker executing frame dequeuing from FrameQueue and triggering
the InferencePipeline processing engine per camera. Updates PresentationFrameBuffer with UI View Models.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Optional

from camera_analytics.adapters.bridge.inference_pipeline import FrameProcessingSummary, InferencePipeline
from camera_analytics.ingestion.models import IngestedFrame
from camera_analytics.ingestion.queue import FrameQueue
from camera_analytics.models.camera import Camera
from camera_analytics.orchestration.states import PipelineState
from camera_analytics.viewer.buffer import PresentationFrameBuffer
from camera_analytics.viewer.builder import FramePresentationBuilder

logger = logging.getLogger(__name__)


class PipelineExecutionWorker:
    """Dedicated background thread worker dequeuing frames from FrameQueue and triggering InferencePipeline."""

    def __init__(
        self,
        pipeline_id: str,
        camera_id: str,
        frame_queue: FrameQueue,
        inference_pipeline: InferencePipeline,
        camera: Optional[Camera] = None,
        metrics_accumulator: Optional[Any] = None,
        aggregator: Optional[Any] = None,
    ) -> None:
        self._pipeline_id = pipeline_id
        self._camera_id = camera_id
        self._frame_queue = frame_queue
        self._inference_pipeline = inference_pipeline
        self._camera = camera or getattr(inference_pipeline, "_camera", None)
        self._metrics_accumulator = metrics_accumulator
        self._aggregator = aggregator

        self._state = PipelineState.CREATED
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Presentation Buffer
        self._presentation_buffer = PresentationFrameBuffer(capacity=5)

        # Worker Metrics
        self._total_processed_frames = 0
        self._last_summary: Optional[FrameProcessingSummary] = None
        self._fps_execution = 0.0

    @property
    def pipeline_id(self) -> str:
        return self._pipeline_id

    @property
    def camera_id(self) -> str:
        return self._camera_id

    @property
    def aggregator(self) -> Optional[Any]:
        return self._aggregator

    @property
    def state(self) -> PipelineState:
        with self._lock:
            return self._state

    @property
    def presentation_buffer(self) -> PresentationFrameBuffer:
        return self._presentation_buffer

    @property
    def total_processed_frames(self) -> int:
        with self._lock:
            return self._total_processed_frames

    @property
    def fps_execution(self) -> float:
        with self._lock:
            return self._fps_execution

    @property
    def last_summary(self) -> Optional[FrameProcessingSummary]:
        with self._lock:
            return self._last_summary

    def start(self) -> bool:
        """Start the background execution worker thread."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                logger.warning("PipelineExecutionWorker[%s]: Already running.", self._pipeline_id)
                return True

            self._stop_event.clear()
            self._pause_event.clear()
            self._thread = threading.Thread(
                target=self._run_loop,
                name=f"PipelineExecutionWorker_{self._pipeline_id}",
                daemon=True,
            )
            self._thread.start()
            logger.info("PipelineExecutionWorker[%s]: Execution thread started.", self._pipeline_id)
            return True

    def stop(self) -> None:
        """Stop background execution worker thread."""
        logger.info("PipelineExecutionWorker[%s]: Stopping execution thread...", self._pipeline_id)
        self._stop_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=2.0)

        with self._lock:
            self._state = PipelineState.STOPPED
            self._inference_pipeline.stop()

        logger.info("PipelineExecutionWorker[%s]: Stopped cleanly.", self._pipeline_id)

    def pause(self) -> None:
        self._pause_event.set()

    def resume(self) -> None:
        self._pause_event.clear()

    def _set_state(self, new_state: PipelineState) -> None:
        with self._lock:
            self._state = new_state

    def _run_loop(self) -> None:
        """Main execution loop dequeuing frames and invoking InferencePipeline."""
        self._set_state(PipelineState.INITIALIZED)
        self._inference_pipeline.initialize()
        self._set_state(PipelineState.RUNNING)

        last_fps_calc_time = time.time()
        fps_frame_count = 0

        while not self._stop_event.is_set():
            if self._pause_event.is_set():
                time.sleep(0.05)
                continue

            # Dequeue IngestedFrame from FrameQueue (Producer-Consumer pattern)
            frame: Optional[IngestedFrame] = self._frame_queue.get(timeout=0.05)
            # logger.info("FRAME RECEIVED")
            if frame is None:
                continue

            try:
                # Trigger InferencePipeline AI processing
                summary = self._inference_pipeline.process_frame(frame)
                # logger.info("FRAME PROCESSED")
                with self._lock:
                    self._total_processed_frames += 1
                    self._last_summary = summary

                # Build FramePresentation view model from AI outputs
                if self._camera is not None:
                    frame_ctx = getattr(self._inference_pipeline, "latest_frame_context", None)
                    presentation = FramePresentationBuilder.build(
                        frame=frame,
                        camera=self._camera,
                        frame_context=frame_ctx,
                        summary=summary,
                        gpu_id=self._inference_pipeline._gpu_id,
                        queue_size=self._frame_queue.size(),
                    )
                    # logger.info("PRESENTATION BUILT")
                    self._presentation_buffer.update(presentation)
                    # logger.info("PRESENTATION UPDATED")
                # Instrument Metrics Accumulator
                if self._metrics_accumulator is not None:
                    self._metrics_accumulator.update_counts(
                        detections_count=summary.detected_persons_count,
                        tracks_count=summary.active_tracks_count,
                    )

                fps_frame_count += 1
                now = time.time()
                if now - last_fps_calc_time >= 1.0:
                    calc_exec_fps = fps_frame_count / (now - last_fps_calc_time)
                    with self._lock:
                        self._fps_execution = calc_exec_fps
                    if self._metrics_accumulator is not None:
                        self._metrics_accumulator.update_execution(
                            fps=calc_exec_fps,
                            pipeline_latency_ms=summary.total_pipeline_latency_ms,
                        )
                        self._metrics_accumulator.update_transport(queue_size=self._frame_queue.size())
                    fps_frame_count = 0
                    last_fps_calc_time = now

            except Exception as exc:
                logger.error("PipelineExecutionWorker[%s]: Exception in InferencePipeline: %s", self._pipeline_id, exc, exc_info=True)
                with self._lock:
                    self._state = PipelineState.FAILED

        self._set_state(PipelineState.STOPPED)
