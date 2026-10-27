"""
Packaging Regression Test Suite for CCTV Analytics AI Engine.

Verifies:
1. RuntimeResourceManager path resolution logic across environments.
2. DistributionValidator & RuntimeEnvironmentAudit logic.
3. Pre-flight verification and distribution.manifest.json integrity.
4. Official `--verify` CLI contract functionality.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from camera_analytics.bootstrap.distribution_validator import (
    DistributionValidator,
    RuntimeEnvironmentAudit,
)
from camera_analytics.bootstrap.first_run import FirstRunBootstrap
from camera_analytics.bootstrap.resource_manager import RuntimeResourceManager


class TestPackagingAndDistribution(unittest.TestCase):
    """Test suite for packaging compatibility and distribution verification."""

    def test_resource_manager_resolution(self) -> None:
        """Test RuntimeResourceManager resolves core files cleanly."""
        rm = RuntimeResourceManager.get_instance()
        self.assertIsNotNone(rm.executable_dir)

        # Test config resolution
        config_path = rm.resolve_config_path()
        self.assertTrue(config_path.exists(), f"Config file should exist: {config_path}")

        # Test model resolution
        model_path = rm.resolve_model_path("yolo26m-pose.pt")
        self.assertTrue(model_path.exists(), f"Model file should exist: {model_path}")

        # Test writable directory creation
        log_dir = rm.resolve_writable_dir("logs")
        self.assertTrue(log_dir.exists(), f"Log dir should exist: {log_dir}")

    def test_distribution_manifest_and_validator(self) -> None:
        """Test DistributionValidator checks distribution.manifest.json."""
        validator = DistributionValidator()
        passed, messages = validator.validate_distribution()

        self.assertTrue(passed, f"Distribution validation should pass: {messages}")
        self.assertTrue(any("[OK] Config" in m for m in messages))
        self.assertTrue(any("[OK] Model Asset" in m for m in messages))

    def test_environment_audit_collection(self) -> None:
        """Test RuntimeEnvironmentAudit collects system metadata."""
        env_data = RuntimeEnvironmentAudit.collect()
        self.assertIn("python_version", env_data)
        self.assertIn("torch_version", env_data)
        self.assertIn("cuda_available", env_data)

    def test_first_run_bootstrap_execution(self) -> None:
        """Test FirstRunBootstrap pre-flight verification."""
        bootstrap = FirstRunBootstrap()
        res = bootstrap.execute(verify_only=False)
        self.assertTrue(res, "FirstRunBootstrap should pass pre-flight checks")


if __name__ == "__main__":
    unittest.main()
