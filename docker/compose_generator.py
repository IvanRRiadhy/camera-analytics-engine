"""
Docker Compose Generator component for CCTV Analytics AI Engine.

Generates production-ready compose.yaml specification files tailored for each build profile.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)


class DockerComposeGenerator:
    """Generator creating production compose.yaml configuration files."""

    @classmethod
    def generate_compose_file(cls, target_dir: Path, profile_data: Dict[str, Any], registry_url: str = "") -> Path:
        """Generate compose.yaml file in target distribution folder.

        Args:
            target_dir: Target output directory
            profile_data: Loaded build profile dictionary
            registry_url: Optional container registry prefix

        Returns:
            Path: Path to generated compose.yaml file
        """
        pkg = profile_data.get("packaging", {})
        raw_tag = pkg.get("image_tag", "aiengine:latest")
        if registry_url:
            image_name = f"{registry_url.rstrip('/')}/{raw_tag}"
        else:
            image_name = raw_tag

        p_name = profile_data.get("profile_name", "docker-release")
        is_jetson = "jetson" in p_name

        runtime_block = "    runtime: nvidia\n" if is_jetson or "gpu" in p_name else ""

        compose_content = f"""# ==============================================================================
# CCTV Analytics AI Engine - Production Docker Compose Specification
# Target Profile : {p_name}
# Image Tag      : {image_name}
# ==============================================================================
services:
  aiengine:
    image: {image_name}
    container_name: aiengine_runtime
{runtime_block}    network_mode: host
    restart: always
    environment:
      - AIENGINE_VERSION={profile_data.get("version", "2.2.1")}
      - TARGET_ENVIRONMENT={profile_data.get("environment", "JETSON_ARM64").upper()}
      - PYTHONUNBUFFERED=1
    volumes:
      - ./logs:/opt/aiengine/logs
      - ./runtime:/opt/aiengine/runtime
      - ./cache:/opt/aiengine/cache
      - ./output:/opt/aiengine/output
      - ./recordings:/opt/aiengine/recordings
      - ./configs:/opt/aiengine/configs
    healthcheck:
      test: ["CMD-SHELL", "python3 -m camera_analytics.main --verify || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 15s
"""
        compose_path = target_dir / "compose.yaml"
        compose_path.write_text(compose_content, encoding="utf-8")
        logger.info("[+] Generated Production Compose Spec: %s", compose_path)
        return compose_path
