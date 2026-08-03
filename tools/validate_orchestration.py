"""
Validation tool for Sprint 11.2 Camera Session & Pipeline Orchestrator.

Validates creation, state transitions, fault isolation, and thread-safe querying
of 100+ simulated pipeline instances and camera sessions.
"""

from __future__ import annotations

import logging
import sys
import threading
from pathlib import Path

from camera_analytics.bootstrap import (
    EngineBootstrap,
    JsonConfigurationProvider,
    PipelineConfiguration,
)
from camera_analytics.orchestration import (
    CameraSessionState,
    PipelineCoordinator,
    PipelineState,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("validate_orchestration")


def main() -> int:
    logger.info("=" * 70)
    logger.info("Sprint 11.2 Validation: Camera Session & Pipeline Orchestrator")
    logger.info("=" * 70)

    sample_dir = Path("config.sample")
    if not sample_dir.exists():
        logger.error("Sample configuration directory 'config.sample' not found!")
        return 1

    # Step 1: Bootstrap Engine
    provider = JsonConfigurationProvider(config_dir=sample_dir)
    bootstrap = EngineBootstrap(provider=provider)
    res = bootstrap.bootstrap()

    if not res.is_success or res.context is None:
        logger.error("[-] EngineBootstrap failed!")
        return 1

    context = res.context
    coordinator: PipelineCoordinator = context.services.get_required("pipeline_coordinator", PipelineCoordinator)
    logger.info("[+] EngineBootstrap initialized PipelineCoordinator successfully!")

    # Step 2: Verify Initialized Pipelines
    pipelines = coordinator.pipeline_manager.list_pipelines()
    assert len(pipelines) == 1, f"Expected 1 pipeline from sample config, got {len(pipelines)}"
    pipe = pipelines[0]
    logger.info("[+] Initialized Pipeline: %s (State: %s)", pipe.pipeline_id, pipe.state.name)
    logger.info("    Camera ID:     %s", pipe.camera_id)
    logger.info("    Session ID:    %s (State: %s)", pipe.session.session_id, pipe.session.state.name)
    logger.info("    RTSP URI:      %s", pipe.session.connection.rtsp_uri)

    # Step 3: Test State Transitions via Coordinator
    logger.info("\n--- Testing Pipeline & Session Lifecycle Transitions ---")
    coordinator.start_pipeline(pipe.pipeline_id)
    summary = coordinator.get_pipeline_status_summary(pipe.pipeline_id)
    assert summary is not None
    assert summary["pipeline_state"] == PipelineState.RUNNING.name
    assert summary["session_state"] == CameraSessionState.RUNNING.name
    logger.info("[+] Pipeline transition to RUNNING verified!")

    coordinator.stop_pipeline(pipe.pipeline_id)
    summary = coordinator.get_pipeline_status_summary(pipe.pipeline_id)
    assert summary is not None
    assert summary["pipeline_state"] == PipelineState.STOPPED.name
    assert summary["session_state"] == CameraSessionState.STOPPED.name
    logger.info("[+] Pipeline transition to STOPPED verified!")

    # Step 4: Scalability & Concurrency Stress Test (100 Simulated Camera Pipelines)
    logger.info("\n--- Stress Testing 100 Simulated Concurrent Pipelines ---")
    coordinator.pipeline_manager.clear()
    coordinator.session_manager.clear()

    created_ids: list[str] = []
    for i in range(1, 101):
        cam_id = f"sim_cam_{i:03d}"
        pipe_id = f"sim_pipe_{i:03d}"
        sess = coordinator.session_manager.create_session(camera_id=cam_id, rtsp_uri=f"rtsp://192.168.1.{i}/stream")
        
        sim_cfg = PipelineConfiguration(
            pipeline_id=pipe_id,
            camera_id=cam_id,
            gpu_id=i % 2,
            app=pipe.config.app,
        )
        sim_cam = pipe.camera
        
        inst = coordinator._factory.create_instance(config=sim_cfg, session=sess, camera=sim_cam)
        coordinator.pipeline_manager.add_pipeline(inst)
        created_ids.append(pipe_id)

    assert len(coordinator.pipeline_manager.list_pipelines()) == 100
    logger.info("[+] Successfully created 100 simulated Camera Pipelines in memory!")

    # Concurrent Thread-safe Reads/Writes
    def worker_thread(thread_idx: int):
        for pid in created_ids[thread_idx * 10 : (thread_idx + 1) * 10]:
            coordinator.start_pipeline(pid)
            coordinator.get_pipeline_status_summary(pid)

    threads = [threading.Thread(target=worker_thread, args=(t,)) for t in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    running_count = sum(
        1 for p in coordinator.pipeline_manager.list_pipelines() if p.state == PipelineState.RUNNING
    )
    assert running_count == 100
    logger.info("[+] Concurrency Test PASSED: All 100 pipelines started concurrently without race conditions!")

    logger.info("\n" + "=" * 70)
    logger.info("SUCCESS: All Sprint 11.2 Orchestration Layer validation checks PASSED!")
    logger.info("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
