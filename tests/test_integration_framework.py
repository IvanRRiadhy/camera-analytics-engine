"""
End-to-End Enterprise Engine Integration Framework Test Suite (Sprint 12.6).

Verifies full end-to-end operational loop:
    1. Node Boot Onboarding: EngineRegistrationService constructs hardware/plugin payload and publishes to cctv.engine.register.
    2. Continuous Telemetry: EngineHeartbeatService gathers CPU/GPU/VRAM metrics and emits 5-second heartbeats.
    3. Control Plane Command Execution: EngineCommandReceiver parses START_PIPELINE / STOP_PIPELINE commands and triggers PipelineCoordinator.
"""

import time
import unittest
from unittest.mock import MagicMock

from camera_analytics.bootstrap import EngineHeartbeatService, EngineRegistrationService
from camera_analytics.orchestration import EngineCommandReceiver


class TestIntegrationFramework(unittest.TestCase):
    """End-to-End Integration Test Suite for Sprint 12.6."""

    def setUp(self) -> None:
        self.instance_id = "engine_test_node_01"
        self.comm_mgr = MagicMock()
        self.pipeline_coord = MagicMock()

    def test_e2e_engine_integration_flow(self) -> None:
        """Test full sequence: Registration -> Heartbeat Emission -> Command Execution."""
        # 1. Registration Phase
        reg_service = EngineRegistrationService(
            instance_id=self.instance_id,
            comm_manager=self.comm_mgr,
        )
        reg_payload = reg_service.register()

        self.assertEqual(reg_payload["instance_id"], self.instance_id)
        self.comm_mgr.publish_raw.assert_called_with(
            "cctv.engine.register",
            f"engine.register.{self.instance_id}",
            reg_payload,
        )

        # 2. Heartbeat Telemetry Phase
        hb_service = EngineHeartbeatService(
            instance_id=self.instance_id,
            comm_manager=self.comm_mgr,
            pipeline_coordinator=self.pipeline_coord,
            interval_sec=0.1,
        )
        hb_service.start()
        time.sleep(0.3)
        hb_service.stop()

        self.assertGreaterEqual(self.comm_mgr.publish_raw.call_count, 2)

        # 3. Remote Control Command Dispatch Phase
        cmd_receiver = EngineCommandReceiver(
            instance_id=self.instance_id,
            comm_manager=self.comm_mgr,
            pipeline_coordinator=self.pipeline_coord,
        )

        cmd_payload = {
            "command_id": "cmd_integration_99",
            "target_instance_id": self.instance_id,
            "command_type": "START_PIPELINE",
            "camera_id": "cam_e2e_01",
            "payload_json": "{\"fps\": 30.0}",
        }

        cmd_result = cmd_receiver.handle_command_payload(cmd_payload)

        self.assertEqual(cmd_result["command_id"], "cmd_integration_99")
        self.assertEqual(cmd_result["status"], "SUCCESS")
        self.pipeline_coord.start_pipeline.assert_called_once_with("cam_e2e_01", {"fps": 30.0})


if __name__ == "__main__":
    unittest.main()
