"""
Enterprise Multi-Target Build Profile Runner for CCTV Analytics AI Engine.

Parses build profile specs (configs/profiles/<profile_name>.json), feature flags,
and executes target packaging actions for Windows, Linux, Jetson, or Docker.
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
logger = logging.getLogger(__name__)


def load_profile(profile_name: str) -> dict:
    """Load build profile JSON file."""
    profile_path = project_root / "configs" / "profiles" / f"{profile_name}.json"
    if not profile_path.exists():
        raise FileNotFoundError(f"Build profile not found: {profile_path}")
    with open(profile_path, "r", encoding="utf-8") as f:
        return json.load(f)


def prepare_release_directory(profile_data: dict) -> Path:
    """Prepare payload directory structure for non-Windows targets."""
    p_name = profile_data["profile_name"]
    target_dir = project_root / "dist" / p_name / "AIEngine"
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    # Copy configs
    configs_dest = target_dir / "configs"
    configs_dest.mkdir(parents=True, exist_ok=True)
    shutil.copy2(project_root / "configs" / "standalone.json", configs_dest / "standalone.json")
    shutil.copy2(project_root / "configs" / "distribution.manifest.json", configs_dest / "distribution.manifest.json")

    # Copy models
    models_dest = target_dir / "models"
    models_dest.mkdir(parents=True, exist_ok=True)
    for model_name in ["yolo26m-pose.pt", "mivolo_v2.torchscript.pt"]:
        m_file = project_root / model_name
        if not m_file.exists():
            m_file = project_root / "camera_analytics" / "models" / "human" / "mivolo" / "weights" / model_name
        if m_file.exists():
            shutil.copy2(m_file, models_dest / m_file.name)

    # Create writable runtime folders
    for wdir in ["logs", "cache", "runtime", "output", "recordings", "exports"]:
        (target_dir / wdir).mkdir(parents=True, exist_ok=True)

    return target_dir


def main() -> int:
    """Main build profile CLI entrypoint."""
    parser = argparse.ArgumentParser(description="Multi-Target Build Profile Runner")
    parser.add_argument(
        "--profile",
        type=str,
        default="windows-release",
        choices=[
            "windows-release", "linux-release", "jetson-release",
            "jetson-nano", "jetson-xavier", "jetson-orin", "docker-release",
            "docker-jetson-nano", "docker-jetson-xavier", "docker-jetson-orin", "docker-x64-gpu", "docker-windows"
        ],
        help="Build profile identifier to execute",
    )
    parser.add_argument(
        "--push",
        action="store_true",
        help="Automatically execute docker push to target container registry after build",
    )
    parser.add_argument(
        "--registry",
        type=str,
        default="",
        help="Container registry URL prefix (e.g., ghcr.io/company or registry.company.com)",
    )
    parser.add_argument(
        "--buildx",
        action="store_true",
        help="Execute docker buildx multi-platform compilation",
    )
    args = parser.parse_args()

    profile_data = load_profile(args.profile)
    flags = profile_data.get("feature_flags", {})

    print("==========================================================")
    print(f"  EXECUTING BUILD PROFILE: {profile_data['profile_name'].upper()}")
    print("==========================================================")
    print(f" Target OS         : {profile_data['target_os']}")
    print(f" Target Arch       : {profile_data['target_arch']}")
    print(f" Packaging Tool    : {profile_data['packaging']['tool']}")
    print(f" Video Backend     : {profile_data['default_backends']['video']}")
    print(f" Inference Backend : {profile_data['default_backends']['inference']}")
    print(f" Studio GUI Flag   : {flags.get('studio_gui', False)}")
    print(f" Headless Flag     : {flags.get('headless_mode', False)}")
    print("==========================================================")

    if profile_data["packaging"]["tool"] == "pyinstaller":
        from camera_analytics.packaging.build_executable import build_executable
        res = build_executable()
        return 0 if res else 1
    elif profile_data["packaging"]["tool"] == "docker":
        from camera_analytics.docker.builder import DockerImageBuilder
        builder = DockerImageBuilder()
        dest_dir = builder.build_and_export(
            profile_data,
            push_to_registry=args.push,
            registry_url=args.registry,
            use_buildx=args.buildx,
        )
        print(f"[+] Docker Build Payload & Script Package Prepared Successfully at: {dest_dir}")
        return 0
    else:
        dest_dir = prepare_release_directory(profile_data)
        print(f"[+] Distribution Payload Prepared Successfully at: {dest_dir}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
