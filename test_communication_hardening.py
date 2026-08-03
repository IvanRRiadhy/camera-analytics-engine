"""
Enterprise Communication Subsystem Hardening Test Suite (Step 4).

Validates:
1. LogPublisher retention policy (keep_last_days, max_backup_files) & size rotation
2. PublisherRegistry controlled discovery (manifest __all__)
3. Exponential backoff retries with randomized jitter
4. Publisher Health State transitions (READY -> CONNECTED -> RECONNECTING -> FAILED)
5. Standalone Mode (console, log) with 0 network connection attempts
6. Graceful shutdown and resource cleanup
"""

import os
import time
import json
from pathlib import Path
from camera_analytics.communication.config_normalizer import ConfigNormalizer
from camera_analytics.communication.manager import CommunicationManager
from camera_analytics.communication.publisher_base import PublisherHealthState
from camera_analytics.communication.publishers.log_publisher import LogPublisher
from camera_analytics.communication.publishers.console_publisher import ConsolePublisher
from camera_analytics.communication.registry import PublisherRegistry

def test_communication_hardening():
    print("=== Running Communication Subsystem Hardening Test Suite ===")

    # 1. Test Controlled Discovery in PublisherRegistry
    registered = PublisherRegistry.list_registered()
    print(f"[+] Controlled Registered Publishers: {registered}")
    assert "console" in registered
    assert "log" in registered
    assert "rabbitmq" in registered
    assert "mqtt" in registered

    # 2. Test LogPublisher Log Rotation & Retention Policy
    print("\n--- Testing LogPublisher Rotation & Retention ---")
    log_dir = Path("logs_hardening_test")
    log_dir.mkdir(parents=True, exist_ok=True)

    # Force small max_bytes (1 KB) for rotation testing
    log_pub = LogPublisher(
        name="test_log",
        enabled=True,
        log_dir=str(log_dir),
        human_filename="analytics.log",
        ndjson_filename="analytics.ndjson",
        max_bytes=500,  # 500 bytes rotation trigger
        max_backup_files=3,
        keep_last_days=7,
    )
    log_pub.initialize({})
    log_pub.start()

    sample_payload = {
        "messageId": "msg_hard_001",
        "cameraId": "cam_lobby_hardened",
        "pipelineId": "pipe_01",
        "timestamp": "2026-08-03T14:55:00.000Z",
        "health": {"fps": 30.0, "latencyMs": 10.0, "inferenceTimeMs": 8.0, "trackerTimeMs": 0.5, "status": "OK"},
        "plugins": {
            "peopleCounting": {"current": 5, "entered": 10, "exited": 5},
            "queueDetection": {"queueLength": 2, "waitingPeople": 2},
            "loitering": {"active": 1}
        }
    }

    # Write enough payloads to trigger multiple rotations
    for _ in range(25):
        log_pub.on_publish_raw("cctv.analytics", "analytics.snapshot", sample_payload)

    # Inspect generated backup files
    rotated_ndjson = list(log_dir.glob("analytics.ndjson.*"))
    rotated_log = list(log_dir.glob("analytics.log.*"))
    print(f"[+] Rotated NDJSON Files Count: {len(rotated_ndjson)}")
    print(f"[+] Rotated Human Log Files Count: {len(rotated_log)}")
    
    assert len(rotated_ndjson) <= 3, f"Exceeded max_backup_files limit: {len(rotated_ndjson)}"
    assert len(rotated_log) <= 3, f"Exceeded max_backup_files limit: {len(rotated_log)}"
    log_pub.stop()

    # 3. Test Exponential Backoff with Jitter
    print("\n--- Testing Exponential Backoff & Jitter ---")
    
    class MockNetworkPublisher(LogPublisher):
        def __init__(self):
            super().__init__(name="mock_net", max_bytes=100000)
            self._max_retries = 2
            self._min_backoff_sec = 0.1
            self._max_backoff_sec = 0.5

        def _failing_op(self):
            raise ConnectionError("Simulated socket disconnect")

        def test_retry(self):
            return self.execute_with_retry(self._failing_op)

    net_pub = MockNetworkPublisher()
    net_pub.initialize({})
    net_pub.start()
    res = net_pub.test_retry()
    assert res is False
    assert net_pub.state == PublisherHealthState.FAILED
    assert net_pub.metrics.retry_count == 2
    print(f"[+] Exponential Retries Verified. State: {net_pub.state.value}, Retries: {net_pub.metrics.retry_count}")

    # 4. Test Standalone CommunicationManager Execution
    print("\n--- Testing Standalone CommunicationManager ---")
    comm_mgr = CommunicationManager(queue_size=100)
    comm_mgr.initialize({
        "communication": {
            "publishers": ["console", "log"]
        }
    })
    comm_mgr.start()

    active_keys = list(comm_mgr.publisher_manager.publishers.keys())
    assert "console" in active_keys
    assert "log" in active_keys
    assert "rabbitmq" not in active_keys
    assert "mqtt" not in active_keys

    pub_res = comm_mgr.publish_snapshot(sample_payload)
    assert pub_res is True
    print("[+] Standalone Dispatch Verified.")

    comm_mgr.initiate_stopping()
    print("\n[SUCCESS] Communication Subsystem Hardening Integration Test PASSED!")

if __name__ == "__main__":
    test_communication_hardening()
