"""
Docker Run Script Generator component for CCTV Analytics AI Engine.

Generates operational shell helper scripts (run.sh, stop.sh, restart.sh, verify.sh) for field deployment.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Any


class DockerRunScriptGenerator:
    """Generator creating host deployment helper scripts."""

    @classmethod
    def generate_scripts(cls, target_dir: Path, profile_data: Dict[str, Any]) -> None:
        """Generate operational shell scripts in target distribution folder.

        Args:
            target_dir: Target directory path
            profile_data: Loaded build profile dictionary
        """
        pkg = profile_data.get("packaging", {})
        image_tag = pkg.get("image_tag", "aiengine:latest")

        # 1. run.sh
        run_sh = f"""#!/usr/bin/env bash
# CCTV Analytics AI Engine Container Runner
CONTAINER_NAME="aiengine_runtime"
IMAGE_TAG="{image_tag}"

echo "[+] Starting AI Engine Container ($IMAGE_TAG)..."

docker run -d \\
  --name "$CONTAINER_NAME" \\
  --runtime=nvidia \\
  --network=host \\
  --restart=always \\
  -v "$(pwd)/logs:/opt/aiengine/logs" \\
  -v "$(pwd)/runtime:/opt/aiengine/runtime" \\
  -v "$(pwd)/cache:/opt/aiengine/cache" \\
  -v "$(pwd)/output:/opt/aiengine/output" \\
  -v "$(pwd)/recordings:/opt/aiengine/recordings" \\
  -v "$(pwd)/configs:/opt/aiengine/configs" \\
  "$IMAGE_TAG"

echo "[+] AI Engine container started successfully."
"""

        # 2. stop.sh
        stop_sh = """#!/usr/bin/env bash
CONTAINER_NAME="aiengine_runtime"
echo "[+] Stopping AI Engine Container..."
docker stop "$CONTAINER_NAME" || true
docker rm "$CONTAINER_NAME" || true
echo "[+] AI Engine container stopped."
"""

        # 3. verify.sh
        verify_sh = f"""#!/usr/bin/env bash
IMAGE_TAG="{image_tag}"
echo "[+] Verifying AI Engine Container Integrity..."
docker run --rm --runtime=nvidia "$IMAGE_TAG" --verify
"""

        (target_dir / "run.sh").write_text(run_sh, encoding="utf-8")
        (target_dir / "stop.sh").write_text(stop_sh, encoding="utf-8")
        (target_dir / "verify.sh").write_text(verify_sh, encoding="utf-8")
