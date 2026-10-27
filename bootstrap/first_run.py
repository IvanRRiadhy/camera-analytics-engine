"""
First-Run Bootstrap Engine & Pre-Flight Verification.

Executes startup environment validation, creates missing writable directories,
validates asset integrity against distribution.manifest.json, and supports the
official enterprise CLI contract: `AIEngine.exe --verify`.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

from camera_analytics.bootstrap.distribution_validator import (
    DistributionValidator,
    RuntimeEnvironmentAudit,
)
from camera_analytics.bootstrap.resource_manager import RuntimeResourceManager

logger = logging.getLogger(__name__)


class FirstRunBootstrap:
    """Handles startup pre-flight validation and directory initialization."""

    def __init__(self, resource_manager: Optional[RuntimeResourceManager] = None) -> None:
        self._rm = resource_manager or RuntimeResourceManager.get_instance()
        self._validator = DistributionValidator(self._rm)

    def execute(self, verify_only: bool = False) -> bool:
        """Execute pre-flight bootstrap sequence.

        Args:
            verify_only: If True (`--verify`), performs validation audit, logs report,
                         and exits with status code 0 (or 1 on error) without starting inference or GUI.

        Returns:
            bool: True if verification passed, False otherwise.
        """
        # 1. Log environment audit
        RuntimeEnvironmentAudit.print_audit_report()

        # 2. Auto-create writable directories
        writable_dirs = ["logs", "cache", "runtime", "output", "recordings", "exports"]
        for wdir in writable_dirs:
            self._rm.resolve_writable_dir(wdir)

        # 3. Perform pre-flight distribution validation
        passed, messages = self._validator.validate_distribution()

        logger.info("==========================================================")
        logger.info("      PRE-FLIGHT DISTRIBUTION VALIDATION REPORT           ")
        logger.info("==========================================================")
        for msg in messages:
            if "[OK]" in msg:
                logger.info(" %s", msg)
            elif "[WARN]" in msg:
                logger.warning(" %s", msg)
            else:
                logger.error(" %s", msg)
        logger.info("==========================================================")

        if not passed:
            logger.critical("Pre-flight distribution verification FAILED! Correct missing assets above.")
            if verify_only:
                sys.exit(1)
            return False

        if verify_only:
            logger.info("PRE-FLIGHT VERIFICATION PASSED SUCCESSFULLY (--verify mode). Exiting cleanly.")
            sys.exit(0)

        return True
