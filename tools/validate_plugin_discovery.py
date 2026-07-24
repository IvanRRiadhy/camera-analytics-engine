"""
Plugin Discovery Framework Validation Tool (Sprint 10G).

Creates sample plugin folder structure (`camera_analytics/plugins/`) with 3 valid manifests and 1 invalid manifest.
Executes PluginDiscovery scanning, converts valid manifests to ModuleDescriptors, registers them into ModuleRegistry,
and prints official Plugin Discovery & Manifest Validation Report.

Usage::

    python -m camera_analytics.tools.validate_plugin_discovery
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from camera_analytics.discovery import PluginDiscovery
from camera_analytics.registry import ModuleRegistry

logger = logging.getLogger("validate_plugin_discovery")


def setup_logging() -> None:
    """Configure logging format."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )


def create_sample_plugins(base_dir: Path) -> None:
    """Create sample plugins/ directory structure with valid and invalid manifest files.

    Args:
        base_dir: Root directory path for plugins (e.g. 'camera_analytics/plugins').
    """
    base_dir.mkdir(parents=True, exist_ok=True)

    # 1. Valid Plugin: People Counter
    p1 = base_dir / "people_counter"
    p1.mkdir(exist_ok=True)
    with open(p1 / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "plugin_id": "people_counter",
                "name": "People Counter Analytics",
                "version": "1.0.0",
                "sdk_version": "1.0.0",
                "entry_point": "camera_analytics.plugins.people.PeopleCounterModule",
                "author": "Vision Analytics Team",
                "description": "Counts people entering/exiting defined polygon zones",
                "capabilities": ["TRACKING", "POSE", "ZONE"],
                "execution_policy": {"execution_mode": "EVERY_FRAME", "interval": 1},
                "priority": 10,
            },
            f,
            indent=2,
        )

    # 2. Valid Plugin: Heatmap Analytics
    p2 = base_dir / "heatmap"
    p2.mkdir(exist_ok=True)
    with open(p2 / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "plugin_id": "heatmap",
                "name": "Heatmap Occupancy Analytics",
                "version": "1.1.0",
                "sdk_version": "1.0.0",
                "entry_point": "camera_analytics.plugins.heatmap.HeatmapModule",
                "author": "Spatial Analytics Team",
                "description": "Generates spatial occupancy heatmaps",
                "capabilities": ["TRACKING", "GROUND_POINT"],
                "execution_policy": {"execution_mode": "INTERVAL", "interval": 10},
                "priority": 30,
            },
            f,
            indent=2,
        )

    # 3. Valid Plugin: Crowd Density Analytics
    p3 = base_dir / "crowd"
    p3.mkdir(exist_ok=True)
    with open(p3 / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "plugin_id": "crowd_density",
                "name": "Crowd Density Analytics",
                "version": "2.0.0",
                "sdk_version": "1.0.0",
                "entry_point": "camera_analytics.plugins.crowd.CrowdDensityModule",
                "author": "Safety Analytics Team",
                "description": "Monitors crowd density thresholds and over-crowding events",
                "capabilities": ["TRACKING", "ZONE"],
                "execution_policy": {"execution_mode": "INTERVAL", "interval": 5},
                "priority": 20,
            },
            f,
            indent=2,
        )

    # 4. Invalid Plugin: Broken Plugin (Missing sdk_version and entry_point)
    p4 = base_dir / "broken_plugin"
    p4.mkdir(exist_ok=True)
    with open(p4 / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "plugin_id": "broken_plugin_v1",
                "name": "Broken Analytics Plugin",
                "version": "0.1.0",
                # missing 'sdk_version' and 'entry_point'
                "author": "Anonymous Developer",
            },
            f,
            indent=2,
        )


def run_discovery_validation(plugins_dir: str = "camera_analytics/plugins") -> None:
    """Run full Plugin Discovery & Manifest validation."""
    setup_logging()

    logger.info("=" * 75)
    logger.info("Sprint 10G -- Plugin Discovery & Manifest Framework Validation")
    logger.info("=" * 75)

    base_path = Path(plugins_dir)
    logger.info("Setting up sample plugins directory structure at '%s'...", base_path)
    create_sample_plugins(base_path)

    # Instantiate PluginDiscovery scanner
    discovery = PluginDiscovery()

    logger.info("Scanning directory tree for manifest.json files (Without Dynamic Import)...")
    report = discovery.discover(base_path)

    # Create ModuleRegistry and register converted descriptors
    registry = ModuleRegistry()
    for manifest in report.valid_plugins:
        desc = manifest.to_descriptor()
        registry.register(desc)

    logger.info("=" * 75)
    logger.info("PLUGIN DISCOVERY & MANIFEST VALIDATION REPORT")
    logger.info("=" * 75)
    logger.info("Total Manifests Found:      %d manifest(s)", report.found_count)
    logger.info("Valid Plugins Discovered:   %d plugin(s)", len(report.valid_plugins))
    logger.info("Invalid Plugins Rejected:    %d plugin(s)", len(report.invalid_plugins))
    logger.info("-" * 75)
    logger.info("VALID DISCOVERED PLUGINS:")
    for manifest in report.valid_plugins:
        logger.info(
            "  - Plugin ID: '%-18s' | Version: %-6s | SDK: %-5s | EntryPoint: %s",
            manifest.plugin_id,
            manifest.version,
            manifest.sdk_version,
            manifest.entry_point,
        )
    logger.info("-" * 75)
    logger.info("INVALID PLUGINS (REJECTED WITH REASON):")
    for inv in report.invalid_plugins:
        logger.info("  - Path:   %s", inv.manifest_path)
        logger.info("    Reason: %s", inv.reason)
    logger.info("-" * 75)
    logger.info("REGISTERED MODULE DESCRIPTORS IN MODULE REGISTRY:")
    for desc in registry.get_all_descriptors():
        logger.info(
            "  - Descriptor ID: '%-18s' | Mode: %-11s | Interval: %2d | Priority: %d",
            desc.module_id,
            desc.execution_policy.execution_mode.name,
            desc.execution_policy.interval,
            desc.priority,
        )
    logger.info("=" * 75)
    logger.info("Sprint 10G Plugin Discovery & Manifest Framework validation complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Plugin Discovery Framework Validation Tool")
    parser.add_argument(
        "--dir",
        type=str,
        default="camera_analytics/plugins",
        help="Path to plugins directory",
    )
    args = parser.parse_args()

    run_discovery_validation(plugins_dir=args.dir)
