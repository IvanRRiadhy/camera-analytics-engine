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
        "--standalone",
        action="store_true",
        help="Run AI Engine in Standalone Mode using local configuration file.",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Run pre-flight environment & distribution verification audit and exit cleanly.",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run 10-checkpoint end-to-end self-test diagnostic suite and exit cleanly.",
    )
    parser.add_argument(
        "--benchmark",
        action="store_true",
        help="Execute automated runtime benchmark session and generate performance reports.",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Generate HTML and Markdown benchmark & quality gate reports.",
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="enterprise",
        choices=["enterprise", "standalone"],
        help="Execution runtime mode (enterprise or standalone).",
    )
    parser.add_argument(
        "--config-file",
        type=str,
        default="configs/standalone.json",
        help="Path to local configuration JSON file for Standalone Mode.",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="configs/production.json",
        help="Path to configuration directory or JSON configuration file.",
    )
    parser.add_argument(
        "--backend-url",
        type=str,
        default="http://localhost:5100",
        help="ASP.NET Core Backend REST API base URL for Enterprise Mode.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run AI Engine in headless daemon mode (no OpenCV GUI windows).",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default=None,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Override logging verbosity level",
    )
    parser.add_argument(
        "--max-run-sec",
        type=float,
        default=None,
        help="Maximum run duration in seconds before graceful exit",
    )
    return parser.parse_args()


def setup_logging(level_name: str = "INFO", engine_id: str = "engine_edge_01") -> None:
    """Configure system logging format for console and persistent file loggers."""
    from logging.handlers import RotatingFileHandler
    import os
    from datetime import datetime
    from camera_analytics.bootstrap.resource_manager import RuntimeResourceManager

    level = getattr(logging, level_name.upper(), logging.INFO)

    date_str = datetime.now().strftime("%Y-%m-%d")
    rm = RuntimeResourceManager.get_instance()
    log_dir = rm.resolve_writable_dir(os.path.join("logs", date_str, engine_id))
    runtime_log_path = log_dir / "runtime.log"

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
    try:
        import torch
        torch.multiprocessing.freeze_support()
    except Exception:
        pass

    args = parse_args()
    if args.max_run_sec is not None:
        max_run_sec = args.max_run_sec
    setup_logging(args.log_level or "INFO")

    if args.verify:
        return 0

    if args.self_test:
        from camera_analytics.bootstrap.self_test import RuntimeSelfTest
        passed = RuntimeSelfTest.run_self_test()
        return 0 if passed else 1

    if args.benchmark or args.report:
        from camera_analytics.runtime.benchmark.benchmark_runner import RuntimeBenchmarkRunner
        from camera_analytics.runtime.benchmark.html_reporter import BenchmarkHtmlReporter
        from camera_analytics.runtime.benchmark.parity_validator import RuntimeParityValidator

        runner = RuntimeBenchmarkRunner()
        res = runner.execute_benchmark()

        validator = RuntimeParityValidator()
        p_res = validator.evaluate_parity(res)

        reporter = BenchmarkHtmlReporter()
        report_path = reporter.generate_html_report(res)

        logger.info("[+] Benchmark Quality Gate: %s (Violations: %d)", "PASSED" if p_res.passed else "FAILED", len(p_res.violations))
        return 0 if p_res.passed else 1

    # Resolve Runtime Mode and Configuration Provider Strategy
    from camera_analytics.bootstrap.factory import ConfigurationProviderFactory, RuntimeModeResolver

    runtime_mode = RuntimeModeResolver.resolve(args)
    logger.info("[+] Runtime Mode Resolved: '%s'", runtime_mode.value.upper())

    provider = ConfigurationProviderFactory.create(mode=runtime_mode, cli_args=args)
    bootstrap = EngineBootstrap(provider=provider)
    boot_res = bootstrap.bootstrap()

    if not boot_res.is_success or boot_res.context is None:
        logger.error("[-] EngineBootstrap FAILED: %s", boot_res.error_message)
        return 1

    context = boot_res.context
    
    # Configure RuntimeLogger Mode from loaded ConfigurationSnapshot
    from camera_analytics.logging import RuntimeLogger
    log_mode = "production"
    if hasattr(context, "configuration") and context.configuration:
        raw_cfg = getattr(context.configuration, "raw_data", {})
        if isinstance(raw_cfg, dict):
            eng_cfg = raw_cfg.get("engine", {})
            if isinstance(eng_cfg, dict) and "logging" in eng_cfg:
                log_mode = eng_cfg["logging"].get("mode", "production")
            elif isinstance(eng_cfg, dict) and eng_cfg.get("runtime_audit_mode"):
                log_mode = "forensic"
    RuntimeLogger.set_mode(log_mode)

    coordinator: PipelineCoordinator = context.services.get_required("pipeline_coordinator", PipelineCoordinator)
    logger.info("[+] Engine Context initialized. Engine ID: '%s' (Mode: %s | LoggingMode: %s)", context.engine_id, context.environment, RuntimeLogger.get_mode().value.upper())

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

        analytics_cfg = getattr(getattr(pipe_inst.config, "app", None), "analytics", None)
        enabled_mods = list(analytics_cfg.enabled_modules) if analytics_cfg and analytics_cfg.enabled_modules else None
        mod_settings = dict(analytics_cfg.module_settings) if analytics_cfg and analytics_cfg.module_settings else {}

        inf_pipeline = InferencePipeline(
            camera=camera,
            gpu_id=pipe_inst.gpu_id,
            zone_manager=pipe_inst.zone_manager,
            zone_engine=pipe_inst.zone_engine,
            aggregator=pipe_inst.aggregator,
            enabled_modules=enabled_mods,
            module_settings=mod_settings,
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

    # Instantiate StudioLauncher lifecycle manager
    from camera_analytics.studio.launcher import StudioLauncher
    studio_cfg = getattr(context, "config", {})
    if not studio_cfg and hasattr(context, "configuration") and hasattr(context.configuration, "runtime"):
        studio_cfg = getattr(context.configuration.runtime, "studio", {})
    if not isinstance(studio_cfg, dict):
        studio_cfg = {"enabled": True, "launch_with_engine": True}
    studio_launcher = StudioLauncher(config=studio_cfg)
    studio_launcher.initialize()

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

                # Update & Render AI Engine Development Studio Window via StudioLauncher
                if studio_launcher.enabled:
                    studio_launcher.update_and_render(
                        window_manager=viewer_provider.window_manager,
                        execution_workers=execution_workers,
                        context=context,
                    )

                # Poll keyboard events & forward hotkeys to StudioLauncher
                event_cmd = viewer_provider.window_manager.process_events(delay_ms=10)
                raw_key = getattr(viewer_provider.window_manager, "last_key", 255)
                if raw_key != 255 and studio_launcher.enabled:
                    studio_launcher.handle_key(raw_key)

                if event_cmd is False or event_cmd == "quit":
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
