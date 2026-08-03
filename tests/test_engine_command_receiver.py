"""
Unit tests for EngineCommandReceiver (Sprint 12.6).
"""

import unittest
from unittest.mock import MagicMock

from camera_analytics.orchestration.command_receiver import EngineCommandReceiver


class TestEngineCommandReceiver(unittest.TestCase):
    """Test suite for EngineCommandReceiver."""

    def test_handle_command_payload_start_pipeline(self) -> None:
        """Test START_PIPELINE command execution."""
        comm_mgr = MagicMock()
        coord = MagicMock()
        receiver = EngineCommandReceiver(instance_id="engine_edge_01", comm_manager=comm_mgr, pipeline_coordinator=coord)

        cmd = {
            "command_id": "cmd_101",
            "target_instance_id": "engine_edge_01",
            "command_type": "START_PIPELINE",
            "camera_id": "cam_lobby_01",
            "payload_json": "{\"fps\": 10.0}",
        }

        result = receiver.handle_command_payload(cmd)

        self.assertEqual(result["command_id"], "cmd_101")
        self.assertEqual(result["status"], "SUCCESS")
        coord.start_pipeline.assert_called_once_with("cam_lobby_01", {"fps": 10.0})

    def test_handle_command_payload_target_mismatch(self) -> None:
        """Test skipping command when target_instance_id belongs to another node."""
        comm_mgr = MagicMock()
        coord = MagicMock()
        receiver = EngineCommandReceiver(instance_id="engine_edge_01", comm_manager=comm_mgr, pipeline_coordinator=coord)

        cmd = {
            "command_id": "cmd_102",
            "target_instance_id": "engine_edge_02",
            "command_type": "START_PIPELINE",
            "camera_id": "cam_lobby_01",
        }

        result = receiver.handle_command_payload(cmd)

        self.assertEqual(result["status"], "SKIPPED")
        coord.start_pipeline.assert_not_called()

    def test_handle_command_payload_invalid_type(self) -> None:
        """Test returning INVALID_COMMAND status for unsupported command type."""
        comm_mgr = MagicMock()
        receiver = EngineCommandReceiver(instance_id="engine_edge_01", comm_manager=comm_mgr)

        cmd = {
            "command_id": "cmd_103",
            "target_instance_id": "engine_edge_01",
            "command_type": "UNKNOWN_ACTION",
        }

        result = receiver.handle_command_payload(cmd)

        self.assertEqual(result["status"], "INVALID_COMMAND")


if __name__ == "__main__":
    unittest.main()
