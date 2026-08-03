"""
CLI validation tool for Heartbeat Timeout Stress & Recovery Simulation (Sprint 12.6).
"""

import datetime
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from camera_analytics.tests.test_stress_heartbeat_timeout import MockEngineInstance


def validate_heartbeat_timeout_stress() -> bool:
    print("=======================================================================")
    print(" SPRINT 12.6 HEARTBEAT TIMEOUT & RECOVERY STRESS SIMULATION")
    print("=======================================================================")

    instance_id = "engine_stress_node_01"
    node = MockEngineInstance(instance_id)
    start_time = datetime.datetime.now(datetime.timezone.utc)

    # Step 1: Active Initial State
    print(f"\n[Step 1] Initializing active node '{instance_id}'...")
    print(f"  [OK] Initial Node State: {node.state}")

    # Step 2: 16-Second Silence Simulation
    print("\n[Step 2] Simulating 16-second network partition (>15s threshold)...")
    t_16s = start_time + datetime.timedelta(seconds=16)
    notes_16 = node.evaluate_timeout(t_16s)
    print(f"  [OK] Evaluated Node State: {node.state}")
    print(f"  [OK] SignalR Notifications Emitted: {notes_16}")
    assert node.state == "DEGRADED", "Expected state DEGRADED after 16s silence"

    # Step 3: 31-Second Silence Simulation
    print("\n[Step 3] Simulating 31-second network partition (>30s threshold)...")
    t_31s = start_time + datetime.timedelta(seconds=31)
    notes_31 = node.evaluate_timeout(t_31s)
    print(f"  [OK] Evaluated Node State: {node.state}")
    print(f"  [OK] SignalR Notifications Emitted: {notes_31}")
    assert node.state == "OFFLINE", "Expected state OFFLINE after 31s silence"

    # Step 4: Node Recovery
    print("\n[Step 4] Resuming heartbeat emission (Node Recovery)...")
    t_rec = start_time + datetime.timedelta(seconds=35)
    node.receive_heartbeat(t_rec)
    print(f"  [OK] Evaluated Node State: {node.state}")
    assert node.state == "ONLINE", "Expected state ONLINE after heartbeat recovery"

    print("\n=======================================================================")
    print(" SUCCESS: ALL HEARTBEAT TIMEOUT STRESS CHECKS PASSED (100% OK)")
    print("=======================================================================")
    return True


if __name__ == "__main__":
    success = validate_heartbeat_timeout_stress()
    sys.exit(0 if success else 1)
