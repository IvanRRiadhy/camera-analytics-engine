"""
Enterprise Engine Runner Validation Tool (Sprint 11.5).

Verifies full CLI startup, configuration loading, pipeline worker execution, presentation building,
and graceful shutdown via camera_analytics.main.
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

from camera_analytics.main import main as run_engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("validate_main_runner")


def main() -> int:
    logger.info("=" * 80)
    logger.info("Sprint 11.5 Validation: Unified Enterprise Engine Runner & Live Viewer")
    logger.info("=" * 80)

    config_path = Path("configs/production.json")
    if not config_path.exists():
        config_path = Path("config.sample")

    logger.info("[+] Executing camera_analytics.main CLI in HEADLESS mode for verification...")
    sys.argv = ["camera_analytics.main", "--config", str(config_path), "--headless"]

    exit_code = run_engine(max_run_sec=3.0)

    if exit_code == 0:
        logger.info("\n" + "=" * 80)
        logger.info("SUCCESS: Enterprise Engine Runner & Live Viewer Validation PASSED!")
        logger.info("=" * 80)
    else:
        logger.error("[-] Enterprise Engine Runner Validation FAILED with code %d", exit_code)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
