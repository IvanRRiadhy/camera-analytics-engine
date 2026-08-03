"""
Validation script for Sprint 11.1 Engine Bootstrap Layer.

Verifies end-to-end configuration loading, zone deserialization, ServiceRegistry population,
CameraCatalog registration, and EngineBootstrap READY state.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from camera_analytics.bootstrap import (
    BootstrapState,
    EngineBootstrap,
    JsonConfigurationProvider,
)
from camera_analytics.catalog import CameraCatalog
from camera_analytics.communication import CommunicationManager
from camera_analytics.models import ZoneType
from camera_analytics.output import OutputProvider

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("validate_bootstrap")


def main() -> int:
    logger.info("=" * 70)
    logger.info("Sprint 11.1 Validation: AI Engine Bootstrap & Configuration Layer")
    logger.info("=" * 70)

    sample_dir = Path("config.sample")
    if not sample_dir.exists():
        logger.error("Sample configuration directory 'config.sample' not found!")
        return 1

    # Step 1: Test JsonConfigurationProvider directly
    logger.info("\n--- 1. Testing JsonConfigurationProvider ---")
    provider = JsonConfigurationProvider(config_dir=sample_dir)

    try:
        snapshot = provider.load()
        logger.info("[+] ConfigurationSnapshot loaded successfully!")
        logger.info("  Engine ID:      %s", snapshot.engine.engine_id)
        logger.info("  Engine Mode:    %s", snapshot.engine.mode)
        logger.info("  Schema Version: %s", snapshot.schema_version)
        logger.info("  Pipelines:      %d", len(snapshot.pipelines))
        logger.info("  Publishers:     %d", len(snapshot.publishers.publishers))
    except Exception as exc:
        logger.error("✗ Failed to load ConfigurationSnapshot: %s", exc, exc_info=True)
        return 1

    # Verify Deserialized Zones
    pipe = snapshot.pipelines[0]
    zones = pipe.app.camera.zones
    logger.info("  Camera '%s' has %d zone(s)", pipe.camera_id, len(zones))
    assert len(zones) == 2, f"Expected 2 deserialized zones, got {len(zones)}"
    assert zones[0].zone_type == ZoneType.REGION
    logger.info("[+] Zone Deserialization verified: %s (%s)", zones[0].name, zones[0].zone_type.name)

    # Step 2: Test EngineBootstrap state machine
    logger.info("\n--- 2. Testing EngineBootstrap Initialization ---")
    bootstrap = EngineBootstrap(provider=provider)
    result = bootstrap.bootstrap()

    if not result.is_success or result.state != BootstrapState.READY:
        logger.error("✗ EngineBootstrap failed! State: %s, Error: %s", result.state, result.error_message)
        return 1

    context = result.context
    assert context is not None
    logger.info("[+] EngineBootstrap reached state READY!")
    logger.info("  Engine Context ID: %s", context.engine_id)
    logger.info("  Registered Services: %s", context.services.list_services())

    # Step 3: Verify ServiceRegistry Services
    logger.info("\n--- 3. Verifying ServiceRegistry Components ---")

    catalog: CameraCatalog = context.services.get_required("camera_catalog", CameraCatalog)
    assert len(catalog) == 1
    camera = catalog.get_required_camera("cam_lobby_01")
    logger.info("[+] CameraCatalog verified: Camera '%s' (Source: %s)", camera.name, camera.source)

    comm_mgr: CommunicationManager = context.services.get_required("communication_manager", CommunicationManager)
    logger.info("[+] CommunicationManager verified in ServiceRegistry")

    human_out: OutputProvider = context.services.get_required("output_human_console", OutputProvider)
    enterprise_out: OutputProvider = context.services.get_required("output_enterprise_event", OutputProvider)
    logger.info("[+] OutputProviders verified: %s, %s", human_out.name, enterprise_out.name)

    logger.info("\n" + "=" * 70)
    logger.info("SUCCESS: All Sprint 11.1 Bootstrap Layer validation checks PASSED!")
    logger.info("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
