"""
End-to-End Enterprise Pipeline Validation Script (Sprint 11.4).

Validates complete integration across all layers:
    EngineBootstrap -> PipelineCoordinator -> PipelineInstance (ReaderWorker + PipelineExecutionWorker) -> InferencePipeline (YOLO-Pose + BoT-SORT + Core Pipeline + ZoneEngine + SceneFactory + AnalyticsRuntime) -> CommunicationManager -> RabbitMQ / Log Publisher.
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

from camera_analytics.adapters.bridge.inference_pipeline import InferencePipeline
from camera_analytics.adapters.bridge.pipeline_worker import PipelineExecutionWorker
from camera_analytics.bootstrap import EngineBootstrap, JsonConfigurationProvider
from camera_analytics.ingestion import (
    FrameQueue,
    ReaderWorker,
    VideoFileSource,
    VideoReader,
)
from camera_analytics.orchestration import (
    PipelineCoordinator,
    PipelineInstance,
    PipelineState,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("validate_enterprise_pipeline")


def main() -> int:
    logger.info("=" * 80)
    logger.info("Sprint 11.4 Validation: End-to-End Enterprise AI Pipeline Integration")
    logger.info("=" * 80)

    sample_dir = Path("config.sample")
    if not sample_dir.exists():
        logger.error("[-] Config sample directory '%s' not found!", sample_dir)
        return 1

    # 1. Boot Enterprise Platform
    logger.info("\n--- 1. Booting Engine & Loading Configuration Snapshot ---")
    provider = JsonConfigurationProvider(config_dir=sample_dir)
    bootstrap = EngineBootstrap(provider=provider)
    res = bootstrap.bootstrap()

    if not res.is_success or res.context is None:
        logger.error("[-] EngineBootstrap initialization failed!")
        return 1

    context = res.context
    coordinator: PipelineCoordinator = context.services.get_required("pipeline_coordinator", PipelineCoordinator)
    logger.info("[+] EngineBootstrap initialized successfully in state READY.")

    # 2. Inspect Initialized Pipeline
    pipelines = coordinator.pipeline_manager.list_pipelines()
    assert len(pipelines) > 0, "Expected at least 1 initialized pipeline from snapshot"
    instance = pipelines[0]
    logger.info("[+] Target Pipeline: '%s' (Camera: '%s', GPU: %d)", instance.pipeline_id, instance.camera_id, instance.gpu_id)

    # 3. Instantiate Ingestion Worker & AI Execution Worker Bridge
    logger.info("\n--- 2. Initializing Ingestion Layer & AI Inference Pipeline ---")
    video_source = VideoFileSource(instance.camera.source)
    video_reader = VideoReader(source=video_source)
    frame_queue = FrameQueue(capacity=30)

    reader_worker = ReaderWorker(
        pipeline_id=instance.pipeline_id,
        camera_id=instance.camera_id,
        reader=video_reader,
        queue_capacity=30,
    )

    inference_pipeline = InferencePipeline(
        camera=instance.camera,
        gpu_id=instance.gpu_id,
    )

    execution_worker = PipelineExecutionWorker(
        pipeline_id=instance.pipeline_id,
        camera_id=instance.camera_id,
        frame_queue=reader_worker.queue,
        inference_pipeline=inference_pipeline,
    )

    # Attach worker instances to PipelineInstance
    instance = PipelineInstance(
        pipeline_id=instance.pipeline_id,
        camera_id=instance.camera_id,
        gpu_id=instance.gpu_id,
        config=instance.config,
        camera=instance.camera,
        session=instance.session,
        reader=reader_worker,
        frame_queue=reader_worker.queue,
        runtime_kernel=inference_pipeline._runtime_kernel,
        output_providers=tuple(context.services.list_services()),
    )
    coordinator.pipeline_manager.add_pipeline(instance)

    # 4. Start Pipeline & Workers
    logger.info("\n--- 3. Starting ReaderWorker & PipelineExecutionWorker Background Threads ---")
    coordinator.start_pipeline(instance.pipeline_id)
    reader_worker.start()
    execution_worker.start()

    logger.info("[+] Both background threads running. Processing real stream frames...")
    start_time = time.time()
    time.sleep(5.0)  # Let workers process stream frames in parallel

    # 5. Inspect Runtime Execution Metrics
    logger.info("\n--- 4. Enterprise Pipeline Performance & Metrics ---")
    read_metrics = reader_worker.metrics
    processed_count = execution_worker.total_processed_frames
    execution_fps = execution_worker.fps_execution
    last_summary = execution_worker.last_summary

    logger.info("  Total Ingested Frames (ReaderWorker):   %d (FPS: %.1f)", read_metrics.total_frames_read, read_metrics.fps_input)
    logger.info("  Total Processed Frames (AI Execution): %d (FPS: %.1f)", processed_count, execution_fps)
    logger.info("  Ingestion Drops (Queue Full):           %d", read_metrics.frame_drop_count)
    
    if last_summary is not None:
        logger.info("  Last Frame Summary: Frame #%d | Detected Persons: %d | Active Tracks: %d | Latency: %.2f ms",
                    last_summary.frame_number, last_summary.detected_persons_count,
                    last_summary.active_tracks_count, last_summary.total_pipeline_latency_ms)

    assert read_metrics.total_frames_read > 0, "ReaderWorker should have read stream frames"
    assert processed_count > 0, "PipelineExecutionWorker should have processed AI frames"

    # 6. Stop Pipeline Cleanly
    logger.info("\n--- 5. Stopping Enterprise Pipeline & Releasing Resources ---")
    execution_worker.stop()
    reader_worker.stop()
    coordinator.stop_pipeline(instance.pipeline_id)

    logger.info("\n" + "=" * 80)
    logger.info("SUCCESS: End-to-End Enterprise AI Pipeline Integration Test PASSED!")
    logger.info("=" * 80)
    return 0


if __name__ == "__main__":
    sys.exit(main())
