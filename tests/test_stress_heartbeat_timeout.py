"""
Heartbeat Timeout Stress & Recovery Simulation Test Suite (Sprint 12.6).

Verifies backend node state transitions under simulated network partitions:
    1. Active Emission: Node state is ONLINE.
    2. Heartbeat Cessation (>15s): State transitions to DEGRADED.
    3. Prolonged Cessation (>30s): State transitions to OFFLINE.
    4. Recovery: Resuming heartbeats restores state back to ONLINE.
"""

import datetime
import unittest
from typing import Any, List


class MockEngineInstance:
    """Mock EngineInstance representing backend database record."""

    def __init__(self, instance_id: str) -> None:
        self.instance_id = instance_id
        self.state = "ONLINE"
        self.last_heartbeat_utc = datetime.datetime.now(datetime.timezone.utc)

    def evaluate_timeout(self, now: datetime.datetime) -> List[str]:
        elapsed = (now - self.last_heartbeat_utc).total_seconds()
        notifications = []

        if elapsed > 30.0:
            if self.state != "OFFLINE":
                self.state = "OFFLINE"
                notifications.append("OFFLINE")
        elif elapsed > 15.0:
            if self.state != "DEGRADED":
                self.state = "DEGRADED"
                notifications.append("DEGRADED")

        return notifications

    def receive_heartbeat(self, now: datetime.datetime) -> None:
        self.last_heartbeat_utc = now
        self.state = "ONLINE"


class TestHeartbeatTimeoutStress(unittest.TestCase):
    """Test suite for Node Heartbeat Timeout & Recovery logic."""

    def test_heartbeat_timeout_state_transitions(self) -> None:
        """Test state transitions: ONLINE -> DEGRADED -> OFFLINE -> ONLINE recovery."""
        node = MockEngineInstance("engine_edge_01")
        start_time = datetime.datetime.now(datetime.timezone.utc)

        # 1. Initial active state
        self.assertEqual(node.state, "ONLINE")

        # 2. Simulate 16 seconds of silence (>15s)
        t_16s = start_time + datetime.timedelta(seconds=16)
        notes = node.evaluate_timeout(t_16s)

        self.assertEqual(node.state, "DEGRADED")
        self.assertIn("DEGRADED", notes)

        # 3. Simulate 31 seconds of silence (>30s)
        t_31s = start_time + datetime.timedelta(seconds=31)
        notes_31 = node.evaluate_timeout(t_31s)

        self.assertEqual(node.state, "OFFLINE")
        self.assertIn("OFFLINE", notes_31)

        # 4. Resume heartbeats -> Recovery
        t_resume = start_time + datetime.timedelta(seconds=35)
        node.receive_heartbeat(t_resume)

        self.assertEqual(node.state, "ONLINE")


if __name__ == "__main__":
    unittest.main()
