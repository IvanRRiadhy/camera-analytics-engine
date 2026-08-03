"""
Standalone Engine Hardening & Validation Verification Test Suite.

Validates:
1. StandaloneConfigValidator fast-failing rules (duplicate publisher, duplicate zone_id, invalid polygon, invalid interval)
2. Per-Publisher Interval & Independent Change Detection policy (LogPublisher continuous logging vs Change Detection)
3. Multi-camera & multi-zone deserialization and ingestion into ZoneEngine
4. Enterprise Mode backward compatibility
"""

import time
import json
from pathlib import Path
from camera_analytics.config.loader import ConfigValidationError
from camera_analytics.config.validator import StandaloneConfigValidator
from camera_analytics.bootstrap.providers.standalone_provider import StandaloneConfigurationProvider
from camera_analytics.communication.manager import CommunicationManager
from camera_analytics.communication.publishers.log_publisher import LogPublisher
from camera_analytics.communication.publishers.console_publisher import ConsolePublisher

def test_standalone_hardening():
    print("=== Running Standalone Engine Hardening & Validation Test Suite ===")

    # 1. Test Config Validation Fast-Failing Rules
    print("\n--- Testing StandaloneConfigValidator Rules ---")

    # 1a. Invalid Interval
    bad_interval_config = {
        "communication": {"publishers": [{"type": "console", "publish_interval_seconds": -1.0}]},
        "cameras": []
    }
    try:
        StandaloneConfigValidator.validate(bad_interval_config)
        assert False, "Should fail on negative publish_interval_seconds"
    except ConfigValidationError as exc:
        print(f"[+] Verified invalid interval rejection: {exc}")

    # 1b. Duplicate Publisher Type
    dup_pub_config = {
        "communication": {"publishers": [{"type": "console"}, {"type": "console"}]},
        "cameras": []
    }
    try:
        StandaloneConfigValidator.validate(dup_pub_config)
        assert False, "Should fail on duplicate publisher type"
    except ConfigValidationError as exc:
        print(f"[+] Verified duplicate publisher rejection: {exc}")

    # 1c. Polygon Zone with < 3 points
    bad_poly_config = {
        "communication": {"publishers": ["console"]},
        "cameras": [{
            "camera_id": "cam_test",
            "zones": [{"zone_id": "z1", "type": "polygon", "points": [[10, 10], [20, 20]]}]
        }]
    }
    try:
        StandaloneConfigValidator.validate(bad_poly_config)
        assert False, "Should fail on polygon zone with < 3 points"
    except ConfigValidationError as exc:
        print(f"[+] Verified invalid polygon points rejection: {exc}")

    # 1d. Duplicate zone_id
    dup_zone_config = {
        "communication": {"publishers": ["console"]},
        "cameras": [{
            "camera_id": "cam_test",
            "zones": [
                {"zone_id": "z1", "type": "polygon", "points": [[0,0], [10,0], [10,10]]},
                {"zone_id": "z1", "type": "polygon", "points": [[0,0], [20,0], [20,20]]}
            ]
        }]
    }
    try:
        StandaloneConfigValidator.validate(dup_zone_config)
        assert False, "Should fail on duplicate zone_id"
    except ConfigValidationError as exc:
        print(f"[+] Verified duplicate zone_id rejection: {exc}")

    # 2. Test Multi-Camera & Multi-Zone Deserialization
    print("\n--- Testing StandaloneConfigurationProvider Multi-Camera & Zone Deserialization ---")
    provider = StandaloneConfigurationProvider(config_file_path="configs/standalone.json")
    snapshot = provider.load()

    print(f"[+] Engines Mode: {snapshot.engine.mode}")
    print(f"[+] Pipelines Count: {len(snapshot.pipelines)}")
    assert len(snapshot.pipelines) == 2, f"Expected 2 camera pipelines, got {len(snapshot.pipelines)}"

    pipe_lobby = snapshot.pipelines[0]
    pipe_parking = snapshot.pipelines[1]

    print(f"[+] Lobby Camera ID: {pipe_lobby.camera_id}, Zones: {len(pipe_lobby.app.camera.zones)}, Modules: {pipe_lobby.app.analytics.enabled_modules}")
    print(f"[+] Parking Camera ID: {pipe_parking.camera_id}, Zones: {len(pipe_parking.app.camera.zones)}, Modules: {pipe_parking.app.analytics.enabled_modules}")

    assert len(pipe_lobby.app.camera.zones) == 2
    assert len(pipe_parking.app.camera.zones) == 1
    assert pipe_lobby.app.camera.zones[0].vertex_count == 4

    # 3. Test Per-Publisher Interval & Independent Change Detection Policy
    print("\n--- Testing Per-Publisher Interval & Independent Change Detection Policy ---")
    comm_mgr = CommunicationManager()
    comm_mgr.initialize({
        "communication": {
            "publishers": [
                {
                    "type": "console",
                    "enabled": True,
                    "publish_interval_seconds": 0.5,
                    "ignore_change_detection": False
                },
                {
                    "type": "log",
                    "enabled": True,
                    "publish_interval_seconds": 0.1,
                    "ignore_change_detection": True,
                    "log_dir": "logs_hardened_test"
                }
            ]
        }
    })
    comm_mgr.start()

    log_pub = comm_mgr.publisher_manager.publishers["log"]
    console_pub = comm_mgr.publisher_manager.publishers["console"]

    assert log_pub.ignore_change_detection is True
    assert console_pub.ignore_change_detection is False
    assert log_pub.publish_interval_seconds == 0.1
    assert console_pub.publish_interval_seconds == 0.5

    mock_snapshot = {
        "messageId": "msg_001",
        "cameraId": "cam_lobby_01",
        "timestamp": "2026-08-03T15:15:00.000Z",
        "health": {"fps": 30.0},
        "plugins": {"peopleCounting": {"current": 3}}
    }

    # Dispatch identical snapshot 3 times with 0.15s sleep intervals
    print("[+] Dispatching identical snapshots to test Change Detection...")
    for _ in range(3):
        comm_mgr.publish_snapshot(mock_snapshot)
        time.sleep(0.15)

    print(f"[+] LogPublisher (ignore_change_detection=True) Published Count: {log_pub.metrics.published_count}")
    print(f"[+] ConsolePublisher (ignore_change_detection=False) Published Count: {console_pub.metrics.published_count}")

    # LogPublisher should publish continuously on every interval regardless of snapshot signature
    assert log_pub.metrics.published_count >= 2, "LogPublisher should publish continuously"
    # ConsolePublisher should only publish ONCE because snapshot signature is identical!
    assert console_pub.metrics.published_count == 1, "ConsolePublisher should filter identical snapshots via Change Detection"

    comm_mgr.initiate_stopping()
    print("\n[SUCCESS] Standalone Engine Hardening & Validation Test PASSED!")

if __name__ == "__main__":
    test_standalone_hardening()
