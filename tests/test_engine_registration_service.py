"""
Unit tests for EngineRegistrationService (Sprint 12.6).
"""

import unittest
from unittest.mock import MagicMock

from camera_analytics.bootstrap.registration_service import EngineRegistrationService


class TestEngineRegistrationService(unittest.TestCase):
    """Test suite for EngineRegistrationService."""

    def test_build_registration_payload_schema(self) -> None:
        """Test registration payload construction matching TDS Section 2.1.1."""
        comm_mgr = MagicMock()
        service = EngineRegistrationService(instance_id="engine_edge_01", comm_manager=comm_mgr)

        payload = service.build_registration_payload()

        self.assertEqual(payload["instance_id"], "engine_edge_01")
        self.assertIn("worker_node_id", payload)
        self.assertIn("hostname", payload)
        self.assertIn("ip_address", payload)
        self.assertIn("os_platform", payload)
        self.assertIn("gpu_info", payload)
        self.assertIn("cpu_info", payload)
        self.assertIn("installed_plugins", payload)

    def test_register_dispatches_message(self) -> None:
        """Test register() dispatches payload through communication manager."""
        comm_mgr = MagicMock()
        service = EngineRegistrationService(instance_id="engine_edge_01", comm_manager=comm_mgr)

        payload = service.register()

        self.assertEqual(payload["instance_id"], "engine_edge_01")
        comm_mgr.publish_raw.assert_called_once_with(
            "cctv.engine.register",
            "engine.register.engine_edge_01",
            payload,
        )


if __name__ == "__main__":
    unittest.main()
