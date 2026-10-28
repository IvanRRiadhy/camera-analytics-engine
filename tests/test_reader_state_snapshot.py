import time
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np

from camera_analytics.ingestion.models import IngestedFrame
from camera_analytics.ingestion.states import ReaderState
from camera_analytics.ingestion.worker import ReaderWorker
from camera_analytics.runtime.analytics.health_monitor import HealthMonitor
from camera_analytics.runtime.analytics.repository import PluginStateRepository
from camera_analytics.runtime.analytics.snapshot_builder import SnapshotBuilder


def test_reader_state_is_separate_field_in_snapshot_health():
    """Test (a): snapshot dict contains readerState alongside status."""
    repo = PluginStateRepository()
    monitor = HealthMonitor()

    cases = [
        (ReaderState.CREATED, "CONNECTING", 0.0),
        (ReaderState.INITIALIZED, "CONNECTING", 0.0),
        (ReaderState.RECONNECTING, "RECONNECTING", 0.0),
        (ReaderState.READING, "STREAMING", time.time()),
        (ReaderState.FAILED, "FAILED", 0.0),
        (ReaderState.STOPPED, "STOPPED", 0.0),
    ]
    for raw_state, expected_reader_state, lf_val in cases:
        fake_reader_worker = SimpleNamespace(state=raw_state, last_frame_time=lf_val)
        fake_exec_worker = SimpleNamespace(
            fps_execution=0.0 if expected_reader_state != "STREAMING" else 25.0,
            total_processed_frames=0 if expected_reader_state != "STREAMING" else 42,
            _is_running=True,
            reader_worker=fake_reader_worker,
        )

        snapshot = SnapshotBuilder.build_snapshot(
            camera_id="cam_test_01",
            pipeline_id="pipeline_cam_test_01",
            repository=repo,
            health_monitor=monitor,
            worker=fake_exec_worker,
        )
        payload = snapshot.to_dict()
        assert "readerState" in payload["health"]
        assert payload["health"]["status"] == "Running"
        assert payload["health"]["readerState"] == expected_reader_state
        assert snapshot.health.reader_state == expected_reader_state

    # Reader worker without last_frame_time gives UNKNOWN, not STREAMING
    fake_unknown_worker = SimpleNamespace(
        fps_execution=25.0,
        total_processed_frames=10,
        _is_running=True,
        reader_worker=SimpleNamespace(state=ReaderState.READING),
    )
    snap_unknown = SnapshotBuilder.build_snapshot(
        camera_id="cam_test_01",
        pipeline_id="pipeline_cam_test_01",
        repository=repo,
        health_monitor=monitor,
        worker=fake_unknown_worker,
    )
    assert snap_unknown.health.reader_state == "UNKNOWN"


class FlappingFakeReader:
    """Fake reader that fails initial open, but succeeds on reconnect."""

    def __init__(self):
        self.open_attempts = 0
        self.reconnect_attempts = 0

    def open(self) -> bool:
        self.open_attempts += 1
        return False  # Fails initial open

    def reconnect(self) -> bool:
        self.reconnect_attempts += 1
        return True  # Succeeds on reconnect

    def read_frame(self, pipeline_id: str, camera_id: str):
        return IngestedFrame(
            pipeline_id=pipeline_id,
            camera_id=camera_id,
            frame_number=1,
            timestamp=time.time(),
            read_latency_ms=1.0,
            image=np.zeros((10, 10, 3), dtype=np.uint8),
            width=10,
            height=10,
            channels=3,
        )

    def close(self):
        pass


def test_reader_state_connecting_reconnecting_streaming_transitions():
    """E3. Backoff test: prove inside the test that global time.sleep is the real function while worker's backoff is stubbed."""
    real_sys_sleep = time.sleep
    assert time.sleep is real_sys_sleep

    fake_reader = FlappingFakeReader()
    worker = ReaderWorker(
        pipeline_id="pipe_flapping_01",
        camera_id="cam_flapping_01",
        reader=fake_reader,
    )

    recorded_states = []
    orig_set_state = worker._set_state

    def recording_set_state(new_state):
        recorded_states.append(new_state)
        return orig_set_state(new_state)

    worker._set_state = recording_set_state

    # Stub worker module's time with real time() and no-op sleep for backoffs
    worker_time_stub = SimpleNamespace(
        time=time.time,
        sleep=lambda s: None,
    )
    with patch("camera_analytics.ingestion.worker.time", worker_time_stub):
        # 1. Prove inside the test that global time.sleep is the real function
        assert time.sleep is real_sys_sleep
        assert time.sleep is not worker_time_stub.sleep

        # 2. Prove real time.sleep sleeps actual duration
        t0 = time.time()
        time.sleep(0.02)
        assert time.time() - t0 >= 0.015

        # 3. Start worker; with backoff stubbed, it reconnects immediately
        started = worker.start()
        assert started

        deadline = time.time() + 5.0
        while worker.state != ReaderState.READING and time.time() < deadline:
            time.sleep(0.01)

        deadline = time.time() + 2.0
        while worker.last_frame_time <= 0.0 and time.time() < deadline:
            time.sleep(0.01)

        worker.stop()

    assert ReaderState.RECONNECTING in recorded_states
    assert ReaderState.READING in recorded_states
    reconnecting_idx = recorded_states.index(ReaderState.RECONNECTING)
    reading_idx = recorded_states.index(ReaderState.READING)
    assert reconnecting_idx < reading_idx


import threading


class ControllableFakeReader:
    """Fake reader supporting controllable modes: no_frames, flowing, and blocking."""

    def __init__(self):
        self.mode = "no_frames"
        self._counter = 0
        self.block_event = threading.Event()

    def open(self) -> bool:
        return True

    def reconnect(self) -> bool:
        return True

    def read_frame(self, pipeline_id: str, camera_id: str):
        if self.mode == "no_frames":
            time.sleep(0.01)
            return None
        elif self.mode == "flowing":
            self._counter += 1
            time.sleep(0.01)
            return IngestedFrame(
                pipeline_id=pipeline_id,
                camera_id=camera_id,
                frame_number=self._counter,
                timestamp=time.time(),
                read_latency_ms=1.0,
                image=np.zeros((10, 10, 3), dtype=np.uint8),
                width=10,
                height=10,
                channels=3,
            )
        else:  # "blocking"
            self.block_event.wait(timeout=2.0)
            return None

    def close(self):
        self.block_event.set()


def test_reader_state_stalled_threshold_transitions():
    """E1. Stalled test: a real ReaderWorker with stalled_after_s=0.3 and a reader that delivers frames then blocks.
    Assert STREAMING then STALLED without writing _last_frame_time by hand.
    """
    repo = PluginStateRepository()
    monitor = HealthMonitor(stalled_after_s=0.3)
    reader = ControllableFakeReader()

    worker = ReaderWorker(
        pipeline_id="pipe_ctrl_01",
        camera_id="cam_ctrl_01",
        reader=reader,
    )

    fake_exec_worker = SimpleNamespace(
        fps_execution=25.0,
        total_processed_frames=0,
        _is_running=True,
        reader_worker=worker,
    )

    worker.start()
    try:
        deadline = time.time() + 3.0
        while worker.state != ReaderState.READING and time.time() < deadline:
            time.sleep(0.01)
        assert worker.state == ReaderState.READING

        # (i) open succeeds, no frames delivered yet -> CONNECTING
        snap1 = SnapshotBuilder.build_snapshot(
            camera_id="cam_ctrl_01",
            pipeline_id="pipe_ctrl_01",
            repository=repo,
            health_monitor=monitor,
            worker=fake_exec_worker,
        )
        assert snap1.health.status == "Running"
        assert snap1.health.reader_state == "CONNECTING"

        # (ii) switch to flowing frames -> STREAMING (stamped naturally, not by hand)
        reader.mode = "flowing"
        deadline = time.time() + 3.0
        while worker.last_frame_time <= 0.0 and time.time() < deadline:
            time.sleep(0.01)
        assert worker.last_frame_time > 0.0

        snap2 = SnapshotBuilder.build_snapshot(
            camera_id="cam_ctrl_01",
            pipeline_id="pipe_ctrl_01",
            repository=repo,
            health_monitor=monitor,
            worker=fake_exec_worker,
        )
        assert snap2.health.status == "Running"
        assert snap2.health.reader_state == "STREAMING"

        # (iii) frames stop, reader blocks -> STALLED after stalled_after_s=0.3
        reader.mode = "blocking"
        time.sleep(0.35)  # exceed 0.3s threshold

        snap3 = SnapshotBuilder.build_snapshot(
            camera_id="cam_ctrl_01",
            pipeline_id="pipe_ctrl_01",
            repository=repo,
            health_monitor=monitor,
            worker=fake_exec_worker,
        )
        assert snap3.health.status == "Running"
        assert snap3.health.reader_state == "STALLED"
    finally:
        reader.block_event.set()
        worker.stop()


def test_reader_state_stalled_fails_when_stamping_disabled(monkeypatch):
    """E1 (cont.): Fix test_reader_state_stalled_fails_when_stamping_disabled:
    Do not patch global time.time. Patch only ReaderWorker's stamping so last_frame_time never updates
    while leaving time.time real. Assert the state is CONNECTING with frames flowing, and that the
    same reader with real stamping gives STREAMING. One failing-by-design comparison without pytest.raises.
    """
    repo = PluginStateRepository()
    monitor = HealthMonitor(stalled_after_s=0.3)
    reader = ControllableFakeReader()
    reader.mode = "flowing"

    # 1. Real stamping run: frames flowing -> STREAMING
    worker_real = ReaderWorker(
        pipeline_id="pipe_real_stamp_01",
        camera_id="cam_real_stamp_01",
        reader=reader,
    )
    fake_exec_real = SimpleNamespace(
        fps_execution=25.0,
        total_processed_frames=1,
        _is_running=True,
        reader_worker=worker_real,
    )
    worker_real.start()
    try:
        deadline = time.time() + 3.0
        while worker_real.last_frame_time <= 0.0 and time.time() < deadline:
            time.sleep(0.01)
        assert worker_real.last_frame_time > 0.0

        snap_real = SnapshotBuilder.build_snapshot(
            camera_id="cam_real_stamp_01",
            pipeline_id="pipe_real_stamp_01",
            repository=repo,
            health_monitor=monitor,
            worker=fake_exec_real,
        )
        assert snap_real.health.reader_state == "STREAMING"
    finally:
        worker_real.stop()

    # 2. Disabled stamping run: patch only ReaderWorker so last_frame_time never updates (0.0)
    # Global time.time remains real and untouched
    t_start = time.time()
    time.sleep(0.01)
    assert time.time() > t_start  # Proves global time.time is real

    class DisabledStampingWorker(ReaderWorker):
        @property
        def last_frame_time(self) -> float:
            return 0.0

    worker_nostamp = DisabledStampingWorker(
        pipeline_id="pipe_nostamp_01",
        camera_id="cam_nostamp_01",
        reader=reader,
    )
    fake_exec_nostamp = SimpleNamespace(
        fps_execution=25.0,
        total_processed_frames=1,
        _is_running=True,
        reader_worker=worker_nostamp,
    )

    worker_nostamp.start()
    try:
        # Wait for frames to actively decode and flow
        deadline = time.time() + 3.0
        while worker_nostamp.metrics.total_frames_read == 0 and time.time() < deadline:
            time.sleep(0.01)
        assert worker_nostamp.metrics.total_frames_read > 0
        # With stamping disabled, last_frame_time never updates from 0.0
        assert worker_nostamp.last_frame_time == 0.0

        snap_nostamp = SnapshotBuilder.build_snapshot(
            camera_id="cam_nostamp_01",
            pipeline_id="pipe_nostamp_01",
            repository=repo,
            health_monitor=monitor,
            worker=fake_exec_nostamp,
        )

        # Assert state is CONNECTING with frames actively flowing
        assert snap_nostamp.health.reader_state == "CONNECTING"

        # Direct failing-by-design comparison between disabled stamping vs real stamping:
        assert snap_nostamp.health.reader_state == "CONNECTING"
        assert snap_real.health.reader_state == "STREAMING"
        assert snap_nostamp.health.reader_state != snap_real.health.reader_state
    finally:
        reader.block_event.set()
        worker_nostamp.stop()


def test_reader_state_queue_full_never_stalled():
    """Queue-full test: capacity-1 queue, no consumer, frames still decoded for >1s -> STREAMING, never STALLED."""
    repo = PluginStateRepository()
    monitor = HealthMonitor(stalled_after_s=0.3)
    reader = ControllableFakeReader()
    reader.mode = "flowing"

    worker = ReaderWorker(
        pipeline_id="pipe_qfull_01",
        camera_id="cam_qfull_01",
        reader=reader,
        queue_capacity=1,
    )

    fake_exec_worker = SimpleNamespace(
        fps_execution=0.0,
        total_processed_frames=0,
        _is_running=True,
        reader_worker=worker,
    )

    worker.start()
    try:
        t_end = time.time() + 1.2
        while time.time() < t_end:
            time.sleep(0.1)
            snap = SnapshotBuilder.build_snapshot(
                camera_id="cam_qfull_01",
                pipeline_id="pipe_qfull_01",
                repository=repo,
                health_monitor=monitor,
                worker=fake_exec_worker,
            )
            if worker.last_frame_time > 0.0:
                assert snap.health.reader_state == "STREAMING"

        assert worker.metrics.frame_drop_count > 0

        final_snap = SnapshotBuilder.build_snapshot(
            camera_id="cam_qfull_01",
            pipeline_id="pipe_qfull_01",
            repository=repo,
            health_monitor=monitor,
            worker=fake_exec_worker,
        )
        assert final_snap.health.reader_state == "STREAMING"
    finally:
        reader.block_event.set()
        worker.stop()


class ReconnectingFakeReader:
    """Fake reader that flows frames, then fails on demand, then succeeds on reconnect and blocks."""

    def __init__(self):
        self.mode = "flowing"
        self._counter = 0
        self.block_event = threading.Event()
        self.reconnected = False

    def open(self) -> bool:
        return True

    def reconnect(self) -> bool:
        self.reconnected = True
        self.mode = "blocking"
        return True

    def read_frame(self, pipeline_id: str, camera_id: str):
        if self.mode == "flowing":
            self._counter += 1
            time.sleep(0.01)
            return IngestedFrame(
                pipeline_id=pipeline_id,
                camera_id=camera_id,
                frame_number=self._counter,
                timestamp=time.time(),
                read_latency_ms=1.0,
                image=np.zeros((10, 10, 3), dtype=np.uint8),
                width=10,
                height=10,
                channels=3,
            )
        elif self.mode == "fail_once":
            self.mode = "blocking"
            return None  # Triggers ReaderWorker's real _handle_reconnect
        else:  # "blocking"
            self.block_event.wait(timeout=2.0)
            return None

    def close(self):
        self.block_event.set()


def test_reader_state_reconnect_drives_real_reconnect():
    """E2. Drive a real reconnect:
    Reader delivers frames, then read_frame returns None, which makes the worker go RECONNECTING;
    reconnect() succeeds; the reader then blocks. Without writing _state or _last_frame_time by hand,
    assert STREAMING -> RECONNECTING -> CONNECTING (no new frame) and never STALLED right after.
    """
    repo = PluginStateRepository()
    monitor = HealthMonitor(stalled_after_s=0.3)

    reader = ReconnectingFakeReader()
    worker = ReaderWorker(
        pipeline_id="pipe_real_reconn_01",
        camera_id="cam_real_reconn_01",
        reader=reader,
    )

    fake_exec_worker = SimpleNamespace(
        fps_execution=25.0,
        total_processed_frames=1,
        _is_running=True,
        reader_worker=worker,
    )

    recorded_states = []
    orig_set_state = worker._set_state

    def tracking_set_state(new_state):
        recorded_states.append(new_state)
        return orig_set_state(new_state)

    worker._set_state = tracking_set_state

    # Stub worker's backoff sleep so reconnection is fast, leaving global sleep untouched
    worker_time_stub = SimpleNamespace(time=time.time, sleep=lambda s: None)
    with patch("camera_analytics.ingestion.worker.time", worker_time_stub):
        worker.start()
        try:
            # 1. Flowing frames -> STREAMING (stamped naturally by worker)
            deadline = time.time() + 3.0
            while worker.last_frame_time <= 0.0 and time.time() < deadline:
                time.sleep(0.01)
            assert worker.last_frame_time > 0.0

            snap_streaming = SnapshotBuilder.build_snapshot(
                camera_id="cam_real_reconn_01",
                pipeline_id="pipe_real_reconn_01",
                repository=repo,
                health_monitor=monitor,
                worker=fake_exec_worker,
            )
            assert snap_streaming.health.reader_state == "STREAMING"

            # 2. Trigger stream failure by returning None from read_frame
            reader.mode = "fail_once"

            # 3. Wait for real reconnect sequence: worker goes RECONNECTING -> reconnect() succeeds -> READING
            deadline = time.time() + 3.0
            while (not reader.reconnected or worker.state != ReaderState.READING) and time.time() < deadline:
                time.sleep(0.01)

            assert reader.reconnected
            assert worker.state == ReaderState.READING
            assert ReaderState.RECONNECTING in recorded_states

            # Assert order: STREAMING (READING) -> RECONNECTING -> READING
            first_reading_idx = recorded_states.index(ReaderState.READING)
            reconnecting_idx = recorded_states.index(ReaderState.RECONNECTING)
            assert reconnecting_idx > first_reading_idx

            # 4. Without writing _last_frame_time by hand, verify it reset to 0.0 on RECONNECTING
            assert worker.last_frame_time == 0.0

            # 5. Snapshot right after reconnect (no new frame has arrived): must be CONNECTING
            snap_reconnected = SnapshotBuilder.build_snapshot(
                camera_id="cam_real_reconn_01",
                pipeline_id="pipe_real_reconn_01",
                repository=repo,
                health_monitor=monitor,
                worker=fake_exec_worker,
            )
            assert snap_reconnected.health.reader_state == "CONNECTING"

            # 6. Wait longer than stalled_after_s=0.3 to prove it is NEVER STALLED right after
            time.sleep(0.35)
            snap_wait = SnapshotBuilder.build_snapshot(
                camera_id="cam_real_reconn_01",
                pipeline_id="pipe_real_reconn_01",
                repository=repo,
                health_monitor=monitor,
                worker=fake_exec_worker,
            )
            assert snap_wait.health.reader_state == "CONNECTING"
            assert snap_wait.health.reader_state != "STALLED"
        finally:
            reader.block_event.set()
            worker.stop()


def test_reader_state_reconnect_without_reset_fails_evaluating_to_stalled(monkeypatch):
    """E2 (cont.): Split buggy-path check into its own test using an in-memory monkeypatch
    of ReaderWorker._set_state (removing the self._last_frame_time = 0.0 reset).
    Shows it fails with the reset removed by evaluating to STALLED instead of CONNECTING.
    """
    repo = PluginStateRepository()
    monitor = HealthMonitor(stalled_after_s=0.3)

    reader = ReconnectingFakeReader()
    worker = ReaderWorker(
        pipeline_id="pipe_buggy_reconn_01",
        camera_id="cam_buggy_reconn_01",
        reader=reader,
    )

    fake_exec_worker = SimpleNamespace(
        fps_execution=25.0,
        total_processed_frames=1,
        _is_running=True,
        reader_worker=worker,
    )

    # In-memory monkeypatch: remove the reset of _last_frame_time on RECONNECTING
    def buggy_set_state(new_state):
        with worker._lock:
            worker._state = new_state
            # BUG: omitted reset:
            # if new_state == ReaderState.RECONNECTING:
            #     self._last_frame_time = 0.0

    monkeypatch.setattr(worker, "_set_state", buggy_set_state)

    worker_time_stub = SimpleNamespace(time=time.time, sleep=lambda s: None)
    with patch("camera_analytics.ingestion.worker.time", worker_time_stub):
        worker.start()
        try:
            # 1. Flowing frames -> worker gets initial frame timestamp
            deadline = time.time() + 3.0
            while worker.last_frame_time <= 0.0 and time.time() < deadline:
                time.sleep(0.01)
            assert worker.last_frame_time > 0.0
            initial_ts = worker.last_frame_time

            # 2. Trigger stream failure
            reader.mode = "fail_once"

            # 3. Wait for reconnect sequence
            deadline = time.time() + 3.0
            while (not reader.reconnected or worker.state != ReaderState.READING) and time.time() < deadline:
                time.sleep(0.01)

            assert reader.reconnected
            assert worker.state == ReaderState.READING

            # 4. Without the reset, last_frame_time is NOT 0.0; it retains the old timestamp
            assert worker.last_frame_time > 0.0
            assert worker.last_frame_time >= initial_ts

            # Wait to ensure time - last_frame_time > 0.3s
            time.sleep(0.35)

            # 5. Snapshot evaluation: evaluates to STALLED instead of CONNECTING!
            snap_buggy = SnapshotBuilder.build_snapshot(
                camera_id="cam_buggy_reconn_01",
                pipeline_id="pipe_buggy_reconn_01",
                repository=repo,
                health_monitor=monitor,
                worker=fake_exec_worker,
            )
            # Proves it evaluates to STALLED (buggy failure) instead of the desired CONNECTING
            assert snap_buggy.health.reader_state == "STALLED"
            assert snap_buggy.health.reader_state != "CONNECTING"
        finally:
            reader.block_event.set()
            worker.stop()
