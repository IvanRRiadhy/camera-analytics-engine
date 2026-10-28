"""
Tests for time-based failure policy in PipelineExecutionWorker and CUDA OOM retry in YOLOPoseAdapter.

Verifies:
1. Time-based failure policy with injectable clock:
   - 5 failing frames spread over 6 s -> not FAILED.
   - Sustained failures >= 10 s -> FAILED.
   - Failure then success resets streak.
   - 100 failures inside window -> warnings rate-limited to <= 1 per 5s, exactly one summary ERROR on FAILED.
2. YOLOPoseAdapter warm-up retry:
   - OOM twice then success -> load succeeds.
   - OOM three times -> raises RuntimeError.
   - Non-OOM error -> raises without retry.
3. Multi-worker isolation (healthy worker keeps processing, process-level check does not exit).
4. Process-level termination (all workers failed -> main() returns 1).
"""

from __future__ import annotations

import logging
import sys
import time
from typing import Optional
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import torch

from camera_analytics.adapters.bridge.inference_pipeline import InferencePipeline
from camera_analytics.adapters.bridge.pipeline_worker import (
    DEFAULT_FAIL_AFTER_S,
    DEFAULT_MIN_FAILURES,
    DEFAULT_WARN_INTERVAL_S,
    PipelineExecutionWorker,
)
from camera_analytics.adapters.detection.yolo_pose_adapter import YOLOPoseAdapter
from camera_analytics.core.detection_set import DetectionSet
from camera_analytics.core.ports import DetectionResult, DetectorPort
from camera_analytics.ingestion.models import IngestedFrame
from camera_analytics.ingestion.queue import FrameQueue
from camera_analytics.main import main
from camera_analytics.models.camera import Camera
from camera_analytics.orchestration.states import PipelineState


class FakeClock:
    """Injectable monotonic test clock."""

    def __init__(self, start: float = 1000.0) -> None:
        self.current = start

    def __call__(self) -> float:
        return self.current

    def advance(self, seconds: float) -> None:
        self.current += seconds


class ControllableDetector(DetectorPort):
    """Detector with controllable failure injection."""

    def __init__(self, fail_count: int = -1, on_detect_hook=None) -> None:
        self.fail_count = fail_count  # -1 means always fail
        self.calls = 0
        self.on_detect_hook = on_detect_hook

    @property
    def name(self) -> str:
        return "ControllableDetector"

    def load(self, model_path: str, device: str = "cpu") -> None:
        pass

    def detect(self, frame: np.ndarray) -> DetectionResult:
        self.calls += 1
        if self.on_detect_hook:
            self.on_detect_hook(self.calls)
        if self.fail_count == -1 or self.calls <= self.fail_count:
            raise RuntimeError(f"Detector failed on call {self.calls}")
        return DetectionResult(
            detections=DetectionSet([]),
            model_name=self.name,
            inference_time_ms=1.0,
        )

    def release(self) -> None:
        pass


def make_test_frame(pipeline_id: str, camera_id: str, idx: int) -> IngestedFrame:
    return IngestedFrame(
        pipeline_id=pipeline_id,
        camera_id=camera_id,
        frame_number=idx,
        timestamp=time.time(),
        read_latency_ms=1.0,
        image=np.zeros((64, 64, 3), dtype=np.uint8),
        width=64,
        height=64,
        channels=3,
    )


def test_failure_policy_5_failures_over_6s_not_failed_sustained_10s_failed(caplog):
    """5 failing frames spread over 6 s -> not FAILED. Sustained failures >= 10 s -> FAILED."""
    clock = FakeClock(start=100.0)

    # Hook advances clock by 1.2s on each detect call
    def advance_detect(call_idx: int):
        if call_idx <= 5:
            clock.advance(1.2)  # 5 calls * 1.2s = 6.0s duration
        else:
            clock.advance(6.0)  # Call 6 pushes streak duration to 10.8s (>= 10.0s)

    detector = ControllableDetector(fail_count=-1, on_detect_hook=advance_detect)
    queue = FrameQueue(capacity=20)
    for i in range(5):
        queue.put(make_test_frame("p1", "c1", i))

    cam = Camera(camera_id="c1", name="Cam 1", source="dummy.mp4")
    pipe = InferencePipeline(camera=cam, detector=detector, enabled_modules=[])

    worker = PipelineExecutionWorker(
        pipeline_id="p1",
        camera_id="c1",
        frame_queue=queue,
        inference_pipeline=pipe,
        min_failures=3,
        fail_after_s=10.0,
        clock=clock,
    )

    with caplog.at_level(logging.WARNING):
        worker.start()
        try:
            # Wait for first 5 frames to process
            deadline = time.time() + 2.0
            while queue.size() > 0 and time.time() < deadline:
                time.sleep(0.02)

            assert queue.size() == 0
            assert worker.consecutive_failures == 5
            # Duration is 6.0s which is < 10.0s -> MUST NOT BE FAILED!
            assert worker.state != PipelineState.FAILED
            assert worker.state == PipelineState.RUNNING

            # Now put 6th failing frame where duration >= 10.0s
            queue.put(make_test_frame("p1", "c1", 5))
            deadline = time.time() + 2.0
            while worker.state != PipelineState.FAILED and time.time() < deadline:
                time.sleep(0.02)

            # Sustained failures >= 10s -> FAILED
            assert worker.state == PipelineState.FAILED
            assert worker.consecutive_failures == 6

            # Exactly one summary ERROR log
            error_records = [r for r in caplog.records if r.levelname == "ERROR" and "reached failure threshold" in r.message]
            assert len(error_records) == 1
            assert "c1" in error_records[0].message
            assert "Pipeline FAILED" in error_records[0].message
        finally:
            worker.stop()


def test_failure_then_success_resets_streak():
    """Failure then success resets the streak."""
    clock = FakeClock(start=500.0)

    # First 3 calls fail (advancing 2s each = 6s streak, count=3, < 10s duration)
    # 4th call succeeds
    def hook(call_idx: int):
        clock.advance(2.0)

    detector = ControllableDetector(fail_count=3, on_detect_hook=hook)
    queue = FrameQueue(capacity=20)
    for i in range(5):
        queue.put(make_test_frame("p2", "c2", i))

    cam = Camera(camera_id="c2", name="Cam 2", source="dummy.mp4")
    pipe = InferencePipeline(camera=cam, detector=detector, enabled_modules=[])

    worker = PipelineExecutionWorker(
        pipeline_id="p2",
        camera_id="c2",
        frame_queue=queue,
        inference_pipeline=pipe,
        min_failures=3,
        fail_after_s=10.0,
        clock=clock,
    )

    worker.start()
    try:
        deadline = time.time() + 3.0
        while queue.size() > 0 and time.time() < deadline:
            time.sleep(0.02)

        assert queue.size() == 0
        # Frame 4 succeeded -> streak reset!
        assert worker.consecutive_failures == 0
        assert worker.first_failure_time is None
        assert worker.state == PipelineState.RUNNING
    finally:
        worker.stop()


def test_one_hundred_failures_warning_rate_limiting(caplog):
    """100 failures inside window -> warning count stays small, one ERROR on FAILED."""
    clock = FakeClock(start=1000.0)

    # 100 calls advance by 0.11s each (total 11.0s, so fails at call ~91)
    def step_clock(call_idx: int):
        clock.advance(0.11)

    detector = ControllableDetector(fail_count=-1, on_detect_hook=step_clock)
    queue = FrameQueue(capacity=150)
    for i in range(100):
        queue.put(make_test_frame("p3", "c3", i))

    cam = Camera(camera_id="c3", name="Cam 3", source="dummy.mp4")
    pipe = InferencePipeline(camera=cam, detector=detector, enabled_modules=[])

    worker = PipelineExecutionWorker(
        pipeline_id="p3",
        camera_id="c3",
        frame_queue=queue,
        inference_pipeline=pipe,
        min_failures=3,
        fail_after_s=10.0,
        clock=clock,
    )

    with caplog.at_level(logging.WARNING):
        worker.start()
        try:
            deadline = time.time() + 4.0
            while worker.state != PipelineState.FAILED and time.time() < deadline:
                time.sleep(0.02)

            assert worker.state == PipelineState.FAILED

            # Warnings rate-limited to at most 1 per 5s: inside 11s duration, should be <= 3 warnings!
            warn_records = [r for r in caplog.records if r.levelname == "WARNING" and "pipeline exception" in r.message]
            assert 1 <= len(warn_records) <= 3

            # Exactly one summary ERROR on FAILED
            error_records = [r for r in caplog.records if r.levelname == "ERROR" and "reached failure threshold" in r.message]
            assert len(error_records) == 1
        finally:
            worker.stop()


def test_yolo_pose_adapter_warmup_oom_twice_then_success():
    """Warm-up: OOM twice then success -> load succeeds."""
    adapter = YOLOPoseAdapter(confidence_threshold=0.5, iou_threshold=0.45)
    call_count = 0
    sleeps = []

    def mock_sleep(s: float):
        sleeps.append(s)

    def mock_model_call(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            raise torch.cuda.OutOfMemoryError("CUDA out of memory. Tried to allocate 500 MiB")
        return MagicMock()

    with patch("ultralytics.YOLO") as MockYOLO, \
         patch("torch.cuda.is_available", return_value=True), \
         patch("torch.cuda.get_device_name", return_value="Mock GPU"), \
         patch("torch.cuda.empty_cache") as mock_empty_cache, \
         patch("gc.collect") as mock_gc:
        instance = MockYOLO.return_value
        instance.side_effect = mock_model_call

        adapter.load("yolov8n-pose.pt", device="cuda", sleep_fn=mock_sleep)

    assert adapter.is_loaded
    assert call_count == 3
    assert len(sleeps) == 2
    assert sleeps == [2.0, 2.0]
    assert mock_gc.call_count == 2
    assert mock_empty_cache.call_count == 2


def test_yolo_pose_adapter_warmup_oom_three_times_raises():
    """Warm-up: OOM three times -> raises RuntimeError."""
    adapter = YOLOPoseAdapter(confidence_threshold=0.5, iou_threshold=0.45)
    call_count = 0
    sleeps = []

    def mock_sleep(s: float):
        sleeps.append(s)

    def mock_model_call(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        raise torch.cuda.OutOfMemoryError("CUDA out of memory. Tried to allocate 1.50 GiB")

    with patch("ultralytics.YOLO") as MockYOLO, \
         patch("torch.cuda.is_available", return_value=True), \
         patch("torch.cuda.get_device_name", return_value="Mock GPU"), \
         patch("torch.cuda.empty_cache"), \
         patch("gc.collect"):
        instance = MockYOLO.return_value
        instance.side_effect = mock_model_call

        with pytest.raises(RuntimeError) as exc_info:
            adapter.load("yolov8n-pose.pt", device="cuda", sleep_fn=mock_sleep)

    assert "CUDA out of memory" in str(exc_info.value)
    assert call_count == 3
    assert len(sleeps) == 2  # Retried on attempt 1 and 2, failed terminally on attempt 3
    assert not adapter.is_loaded


def test_yolo_pose_adapter_warmup_non_oom_error_no_retry():
    """Warm-up: Non-OOM error -> raises without retry."""
    adapter = YOLOPoseAdapter(confidence_threshold=0.5, iou_threshold=0.45)
    call_count = 0
    sleeps = []

    def mock_sleep(s: float):
        sleeps.append(s)

    def mock_model_call(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        raise ValueError("Invalid model architecture tensor configuration")

    with patch("ultralytics.YOLO") as MockYOLO, \
         patch("torch.cuda.is_available", return_value=True), \
         patch("torch.cuda.get_device_name", return_value="Mock GPU"):
        instance = MockYOLO.return_value
        instance.side_effect = mock_model_call

        with pytest.raises(RuntimeError) as exc_info:
            adapter.load("yolov8n-pose.pt", device="cuda", sleep_fn=mock_sleep)

    assert "Invalid model architecture" in str(exc_info.value)
    assert call_count == 1  # Raised immediately on attempt 1
    assert len(sleeps) == 0  # Zero retries
    assert not adapter.is_loaded


def test_two_workers_one_failing_one_healthy():
    """Two workers, one always failing and one healthy: healthy keeps processing, process does not exit."""
    clock = FakeClock(start=2000.0)

    # Failing detector advances clock by 3.0s per call so it reaches 12s in 4 calls
    def fail_hook(call_idx: int):
        clock.advance(3.0)

    queue_fail = FrameQueue(capacity=20)
    for i in range(10):
        queue_fail.put(make_test_frame("pipe_fail", "cam_fail", i))

    queue_ok = FrameQueue(capacity=20)
    for i in range(10):
        queue_ok.put(make_test_frame("pipe_ok", "cam_ok", i))

    cam_fail = Camera(camera_id="cam_fail", name="Fail Cam", source="dummy.mp4")
    pipe_fail = InferencePipeline(camera=cam_fail, detector=ControllableDetector(fail_count=-1, on_detect_hook=fail_hook), enabled_modules=[])

    cam_ok = Camera(camera_id="cam_ok", name="OK Cam", source="dummy.mp4")
    pipe_ok = InferencePipeline(camera=cam_ok, detector=ControllableDetector(fail_count=0), enabled_modules=[])

    worker_fail = PipelineExecutionWorker(
        pipeline_id="pipe_fail",
        camera_id="cam_fail",
        frame_queue=queue_fail,
        inference_pipeline=pipe_fail,
        min_failures=3,
        fail_after_s=10.0,
        clock=clock,
    )

    worker_ok = PipelineExecutionWorker(
        pipeline_id="pipe_ok",
        camera_id="cam_ok",
        frame_queue=queue_ok,
        inference_pipeline=pipe_ok,
        min_failures=3,
        fail_after_s=10.0,
        clock=clock,
    )

    worker_fail.start()
    worker_ok.start()
    try:
        deadline = time.time() + 3.0
        while (worker_fail.state != PipelineState.FAILED or queue_ok.size() > 0) and time.time() < deadline:
            time.sleep(0.02)

        assert worker_fail.state == PipelineState.FAILED
        assert queue_ok.size() == 0
        assert worker_ok.state == PipelineState.RUNNING
        assert worker_ok.total_processed_frames >= 10

        execution_workers = [worker_fail, worker_ok]
        all_failed = all(ew.state == PipelineState.FAILED for ew in execution_workers)
        assert not all_failed, "Process check must not consider all workers failed when one is healthy"
    finally:
        worker_fail.stop()
        worker_ok.stop()


def test_all_workers_failed_main_returns_one(tmp_path, caplog, capsys):
    """All workers failed: main returns 1 (fake config/detector, no GPU)."""
    cfg_file = tmp_path / "test_all_fail.json"
    cfg_file.write_text("""{
        "schema_version": "2.0.0",
        "cameras": [
            {
                "camera_id": "cam_all_fail",
                "name": "All Fail Camera",
                "source": "dummy.mp4",
                "enabled": true
            }
        ]
    }""", encoding="utf-8")

    test_args = [
        "camera_analytics.main",
        "--standalone",
        "--config-file", str(cfg_file),
        "--headless",
        "--max-run-sec", "5",
    ]

    class FakeVideoSource:
        def open(self):
            return True
        def is_open(self):
            return True
        def read_packet(self):
            time.sleep(0.01)
            from camera_analytics.ingestion.models import StreamPacket
            return StreamPacket(data=b"fake", timestamp=time.time(), is_eof=False, payload=b"fake")
        def close(self):
            pass

    frame_num = 0
    # Simulate time advancing 3.0s per frame so 4 frames exceed 10s
    simulated_time = 3000.0
    def fake_read_frame(self, pipeline_id, camera_id):
        nonlocal frame_num, simulated_time
        frame_num += 1
        simulated_time += 3.0
        time.sleep(0.01)
        return IngestedFrame(
            pipeline_id=pipeline_id,
            camera_id=camera_id,
            frame_number=frame_num,
            timestamp=simulated_time,
            read_latency_ms=1.0,
            image=np.zeros((10, 10, 3), dtype=np.uint8),
            width=10,
            height=10,
            channels=3,
        )

    def fake_clock():
        return simulated_time

    with patch.object(sys, "argv", test_args), \
         patch("camera_analytics.ingestion.sources.factory.create_video_source", return_value=FakeVideoSource()), \
         patch("camera_analytics.ingestion.reader.VideoReader.read_frame", fake_read_frame), \
         patch("time.monotonic", fake_clock), \
         patch("camera_analytics.adapters.bridge.inference_pipeline.InferencePipeline._create_default_detector", return_value=ControllableDetector(fail_count=-1)):
        exit_code = main()

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "reached FAILED state. Exiting." in captured.out or any("reached FAILED state. Exiting." in r.message for r in caplog.records)
