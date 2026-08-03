"""
Unit tests for EngineHeartbeatService (Sprint 12.6).
"""

import time
import unittest
from unittest.mock import MagicMock

from camera_analytics.bootstrap.heartbeat_service import EngineHeartbeatService


class TestEngineHeartbeatService(unittest.TestCase):
    """Test suite for EngineHeartbeatService."""

    def test_heartbeat_service_lifecycle_and_emission(self) -> None:
        """Test starting and stopping heartbeat service emits periodic messages."""
        comm_mgr = MagicMock()
        service = EngineHeartbeatService(
            instance_id="engine_edge_01",
            comm_manager=comm_mgr,
            interval_sec=0.2,
        )

        service.start()
        time.sleep(0.5)
        service.stop()

        self.assertFalse(service._is_running)
        self.assertGreaterEqual(comm_mgr.publish_raw.call_count, 1)

        # Check call arguments
        call_args = comm_mgr.publish_raw.call_args_list[0]
        self.assertEqual(call_args[0][0], "cctv.engine.heartbeat")
        self.assertEqual(call_args[0][1], "engine.heartbeat.engine_edge_01")
        payload = call_args[0][2]

        self.assertEqual(payload["instance_id"], "engine_edge_01")
        self.assertIn("system_metrics", payload)
        self.assertIn("pipelines", payload)
        self.assertIn("service_runtime", payload)


if __name__ == "__main__":
    unittest.main()
