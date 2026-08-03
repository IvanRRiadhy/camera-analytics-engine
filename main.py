"""
Enterprise AI Engine Main CLI Entry Point.

Executes complete platform startup, configuration loading, background pipeline management,
live viewer presentation, signal handling, and graceful shutdown.

Usage::

    python -m camera_analytics.main --config configs/production.json
    python -m camera_analytics.main --config configs/production.json --headless
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import time
from pathlib import Path
from typing import Optional

from camera_analytics.adapters.bridge.inference_pipeline import InferencePipeline
from camera_analytics.adapters.bridge.pipeline_worker import PipelineExecutionWorker
from camera_analytics.bootstrap import EngineBootstrap, JsonConfigurationProvider
from camera_analytics.ingestion import (
    FrameBuffer,
    FrameQueue,
    ReaderWorker,
    VideoFileSource,
    VideoReader,
)
from camera_analytics.orchestration import (
    PipelineCoordinator,
    PipelineInstance,
)
from camera_analytics.viewer import (
    FramePresentationBuilder,
    ViewerProvider,
)

logger = logging.getLogger("camera_analytics.main")


def parse_args() -> argparse.Namespace:
    """Parse CLI command line arguments."""
    parser = argparse.ArgumentParser(
        description="Enterprise CCTV Analytics Platform AI Engine Runner",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config",
        help="Path to configuration directory or JSON configuration file.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run AI Engine in headless daemon mode (no OpenCV GUI windows).",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity level.",
    )
    return parser.parse_args()


def setup_logging(level_name: str = "INFO", engine_id: str = "engine_edge_01") -> None:
    """Configure system logging format for console and persistent file loggers."""
    from logging.handlers import RotatingFileHandler
    import os
    from datetime import datetime

    level = getattr(logging, level_name.upper(), logging.INFO)

    date_str = datetime.now().strftime("%Y-%m-%d")
    log_dir = os.path.join("logs", date_str, engine_id)
    os.makedirs(log_dir, exist_ok=True)
    runtime_log_path = os.path.join(log_dir, "runtime.log")

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        runtime_log_path, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers.clear()
    root_logger.addHandler(stdout_handler)
    root_logger.addHandler(file_handler)


def main(max_run_sec: Optional[float] = None) -> int:
    args = parse_args()
    setup_logging(args.log_level)

    logger.info("=" * 80)
    logger.info("Enterprise CCTV Analytics Platform — AI Engine Core v1.5.0")
    logger.info("=" * 80)

    # 1. Load Configuration Snapshot & Bootstrap Platform from Backend REST API
    from camera_analytics.bootstrap.providers.backend_provider import BackendConfigurationProvider
    
    logger.info("[+] Loading Runtime Configuration Snapshot from ASP.NET Core Backend API (http://localhost:5100)...")
    provider = BackendConfigurationProvider(backend_url="http://localhost:5100")
    bootstrap = EngineBootstrap(provider=provider)
    boot_res = bootstrap.bootstrap()

    if not boot_res.is_success or boot_res.context is None:
        logger.error("[-] EngineBootstrap FAILED: %s", boot_res.error_message)
        return 1

    context = boot_res.context
    coordinator: PipelineCoordinator = context.services.get_required("pipeline_coordinator", PipelineCoordinator)
    logger.info("[+] Engine Context initialized. Engine ID: '%s' (Mode: %s)", context.engine_id, context.environment)

    # 2. Instantiate Ingestion Workers, AI Execution Workers & Viewer Provider
    pipelines = coordinator.pipeline_manager.list_pipelines()
    if len(pipelines) == 0:
        logger.error("[-] No pipelines configured in ConfigurationSnapshot!")
        return 1

    # Register RuntimeMetricsRegistry in system container
    from camera_analytics.telemetry.registry import RuntimeMetricsRegistry
    metrics_registry = RuntimeMetricsRegistry()
    context.services.register("metrics_registry", metrics_registry)

    logger.info("[+] Initializing %d pipeline worker(s)...", len(pipelines))
    reader_workers: list[ReaderWorker] = []
    execution_workers: list[PipelineExecutionWorker] = []

    viewer_provider: Optional[ViewerProvider] = None
    if not args.headless:
        viewer_provider = ViewerProvider(name="opencv_viewer", enabled=True)
        context.services.register("viewer_provider", viewer_provider)

    from camera_analytics.ingestion.sources.factory import create_video_source

    for pipe_inst in pipelines:
        camera = pipe_inst.camera
        video_source = create_video_source(camera.source)
        video_reader = VideoReader(source=video_source)

        # Create isolated PipelineMetricsAccumulator per pipeline
        acc = metrics_registry.create_pipeline(
            pipeline_id=pipe_inst.pipeline_id,
            camera_id=pipe_inst.camera_id,
            camera_name=camera.name,
            queue_capacity=30,
        )

        r_worker = ReaderWorker(
            pipeline_id=pipe_inst.pipeline_id,
            camera_id=pipe_inst.camera_id,
            reader=video_reader,
            queue_capacity=30,
            metrics_accumulator=acc,
        )

        inf_pipeline = InferencePipeline(
            camera=camera,
            gpu_id=pipe_inst.gpu_id,
            zone_manager=pipe_inst.zone_manager,
            zone_engine=pipe_inst.zone_engine,
            aggregator=pipe_inst.aggregator,
        )

        e_worker = PipelineExecutionWorker(
            pipeline_id=pipe_inst.pipeline_id,
            camera_id=pipe_inst.camera_id,
            frame_queue=r_worker.queue,
            inference_pipeline=inf_pipeline,
            metrics_accumulator=acc,
            aggregator=pipe_inst.aggregator,
        )

        reader_workers.append(r_worker)
        execution_workers.append(e_worker)

    from camera_analytics.runtime.analytics import SnapshotPublisher
    comm_mgr = context.services.get("communication_manager")
    snapshot_publisher = SnapshotPublisher(
        coordinator=coordinator,
        execution_workers=execution_workers,
        comm_manager=comm_mgr,
        publish_interval_sec=2.0,
        enable_change_detection=True,
        engine_id=context.engine_id,
    )

    # 3. Register Graceful OS Signal Handlers
    stop_signal_received = False

    def signal_handler(signum: int, frame: Any) -> None:
        nonlocal stop_signal_received
        logger.info("\n[!] Received OS shutdown signal (%s). Initiating graceful shutdown...", signum)
        stop_signal_received = True

        # IMMEDIATELY stop Runtime Snapshot generation and reject new events upon CTRL+C
        if snapshot_publisher is not None:
            snapshot_publisher.stop()
        if comm_mgr is not None and hasattr(comm_mgr, "initiate_stopping"):
            comm_mgr.initiate_stopping()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 4. Start Pipelines, Background Threads & Runtime Snapshot Publisher
    logger.info("[+] Starting all Pipeline Workers...")
    coordinator.start_all_pipelines()
    for rw in reader_workers:
        rw.start()
    for ew in execution_workers:
        ew.start()

    if comm_mgr is not None and hasattr(comm_mgr, "start"):
        comm_mgr.start()

    snapshot_publisher.start()

    logger.info("[+] All workers and 1Hz Runtime Snapshot Publisher started successfully. Engine running!")
    if args.headless:
        logger.info("[+] Engine running in HEADLESS mode. Press Ctrl+C to stop.")

    # 5. Main Execution Loop & Viewer Rendering
    start_run_time = time.time()
    try:
        while not stop_signal_received:
            if max_run_sec is not None and (time.time() - start_run_time) >= max_run_sec:
                logger.info("[+] Target run duration (%.1fs) reached. Stopping loop.", max_run_sec)
                break
            if viewer_provider is not None:
                # Render live view for each camera pipeline via FramePresentationBuilder
                for i, pipe_inst in enumerate(pipelines):
                    r_worker = reader_workers[i]
                    e_worker = execution_workers[i]

                    # Retrieve latest completed FramePresentation View Model from AI Execution Worker
                    presentation = e_worker.presentation_buffer.get_latest()
                    if presentation is not None:
                        viewer_provider.render_presentation(presentation)

                # Poll keyboard events
                event_cmd = viewer_provider.window_manager.process_events(delay_ms=10)
                if event_cmd == "quit":
                    logger.info("[!] User pressed 'q' / ESC key. Shutting down...")
                    break
            else:
                time.sleep(0.1)

    except KeyboardInterrupt:
        logger.info("[!] KeyboardInterrupt caught. Shutting down...")
    except Exception as exc:
        logger.error("[-] Engine Main Loop Exception: %s", exc, exc_info=True)

    # 6. Graceful Shutdown & Resource Disposal (Strict Layered Shutdown Order)
    logger.info("[+] Executing Graceful Engine Shutdown...")
    if viewer_provider is not None:
        viewer_provider.close()

    # STAGE 1: Stop Frame Ingestion (Reader Workers)
    for rw in reader_workers:
        rw.stop()

    # STAGE 2: Stop AI Execution Workers (Pipeline Execution Workers)
    for ew in execution_workers:
        ew.stop()

    # STAGE 3: Stop Pipeline Coordinator Sessions
    coordinator.stop_all_pipelines()

    # STAGE 4: Stop Node Heartbeat Service
    hb_svc = context.services.get("heartbeat_service")
    if hb_svc is not None and hasattr(hb_svc, "stop"):
        hb_svc.stop()

    # STAGE 5: Stop 1Hz Runtime Snapshot Publisher & Runtime Event Bus
    if snapshot_publisher is not None:
        snapshot_publisher.stop()

    from camera_analytics.events.bus import RuntimeEventBus
    event_bus = RuntimeEventBus.get_instance()
    if hasattr(event_bus, "stop"):
        event_bus.stop()

    # STAGE 6: Drain & Stop Communication Manager (flushes queue and closes publishers AFTER queue is empty)
    if comm_mgr is not None and hasattr(comm_mgr, "stop"):
        comm_mgr.stop()
        comm_mgr.dispose()

    logger.info("=" * 80)
    logger.info("Enterprise CCTV Analytics Engine shutdown complete. Goodbye!")
    logger.info("=" * 80)
    return 0


if __name__ == "__main__":
    sys.exit(main())
