"""
Automated PyInstaller Executable Builder for CCTV Analytics AI Engine.

Executes PyInstaller build using `ai_engine.spec`, copies required models, configs,
and plugins to `dist/AIEngine/`, and runs `--verify` validation on the generated binary.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, List, Optional, Tuple

project_root = Path(__file__).resolve().parent.parent.parent
dist_dir = project_root / "dist" / "AIEngine"


def create_faces_readme(readme_path: Path | str) -> None:
    """Create README.txt inside face gallery directory explaining format and biometric notice."""
    p = Path(readme_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    content = """Face Gallery Directory for CCTV Analytics Face Matching Plugin
================================================================

LAYOUT:
To enroll identity profiles, place one of the following layouts in this folder:

Option 1: Flat Image & Metadata
  <person_id>.jpg (or .png, .jpeg, .webp)
  <person_id>_meta.json

Option 2: Subdirectory with Multiple Images per Identity
  <person_id>/
    image1.jpg
    image2.jpg
    meta.json

METADATA FORMAT (<person_id>_meta.json or meta.json):
{
  "person_id": "P0001",
  "full_name": "Full Name",
  "department": "Security",
  "role": "Staff"
}

ENROLLMENT REQUIREMENTS:
- Exactly 1 face detected per image.
- Face bounding box width >= 80 pixels.
- Near-frontal pose (eye-line tilt < 20 degrees, nose centered horizontally).
- Composite face quality score >= 0.30.

PRIVACY & COMPLIANCE NOTICE:
Facial photos and embedding templates constitute sensitive biometric personal data.
Processing of biometric data must strictly comply with Indonesia's Personal Data Protection Law
(Undang-Undang No. 27 Tahun 2022 tentang Pelindungan Data Pribadi / UU PDP).
Obtaining lawful consent from data subjects and defining compliant retention periods are the sole
responsibility of the system operator. Secure access to this directory and store data responsibly.
"""
    p.write_text(content, encoding="utf-8")


def get_plugin_ignore_patterns(with_lpr: bool = False, with_fr: bool = False) -> list[str]:
    """Return directory names to ignore when copying plugins folder into distribution."""
    ignores = []
    if not with_lpr:
        ignores.append("vehicle_lpr")
    if not with_fr:
        ignores.append("face_matching")
    return ignores


def sanitize_weight_paths(config_path: Path | str, verbose: bool = True) -> list[tuple[str, Any]]:
    """Sanitize vehicle_lpr and face_matching settings in a configuration file by removing weight path keys.

    Deletes 'detector_weights' and 'reader_weights' in every vehicle_lpr settings block,
    and 'yunet_weights' and 'sface_weights' in every face_matching settings block,
    allowing frozen executables to fall back to bundled default model weights.
    Keeps 'gallery_path' and all other keys. Rewrites config as UTF-8 only if keys were removed.

    Args:
        config_path: Path to JSON configuration file.
        verbose: Whether to print sanitization logs to stdout.

    Returns:
        List of (key, old_value) tuples for all removed keys.
    """
    cfg_file = Path(config_path)
    if not cfg_file.is_file():
        return []

    with open(cfg_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        return []

    lpr_blocks: list[dict[str, Any]] = []
    fr_blocks: list[dict[str, Any]] = []
    seen_ids = set()

    def _add_lpr_block(d: Any) -> None:
        if isinstance(d, dict) and id(d) not in seen_ids:
            seen_ids.add(id(d))
            lpr_blocks.append(d)

    def _add_fr_block(d: Any) -> None:
        if isinstance(d, dict) and id(d) not in seen_ids:
            seen_ids.add(id(d))
            fr_blocks.append(d)

    # 1. Top-level module_settings
    ms = data.get("module_settings")
    if isinstance(ms, dict):
        if isinstance(ms.get("vehicle_lpr"), dict):
            _add_lpr_block(ms["vehicle_lpr"])
        if isinstance(ms.get("face_matching"), dict):
            _add_fr_block(ms["face_matching"])

    # 2. Analytics-nested forms at top level:
    ana = data.get("analytics")
    if isinstance(ana, dict):
        ana_ms = ana.get("module_settings")
        if isinstance(ana_ms, dict):
            if isinstance(ana_ms.get("vehicle_lpr"), dict):
                _add_lpr_block(ana_ms["vehicle_lpr"])
            if isinstance(ana_ms.get("face_matching"), dict):
                _add_fr_block(ana_ms["face_matching"])
        ana_mods = ana.get("modules")
        if isinstance(ana_mods, dict):
            if isinstance(ana_mods.get("vehicle_lpr"), dict):
                _add_lpr_block(ana_mods["vehicle_lpr"])
            if isinstance(ana_mods.get("face_matching"), dict):
                _add_fr_block(ana_mods["face_matching"])

    # 3. Cameras list forms:
    cams = data.get("cameras")
    if isinstance(cams, list):
        for cam in cams:
            if isinstance(cam, dict):
                cam_ms = cam.get("module_settings")
                if isinstance(cam_ms, dict):
                    if isinstance(cam_ms.get("vehicle_lpr"), dict):
                        _add_lpr_block(cam_ms["vehicle_lpr"])
                    if isinstance(cam_ms.get("face_matching"), dict):
                        _add_fr_block(cam_ms["face_matching"])
                cam_ana = cam.get("analytics")
                if isinstance(cam_ana, dict):
                    cam_ana_ms = cam_ana.get("module_settings")
                    if isinstance(cam_ana_ms, dict):
                        if isinstance(cam_ana_ms.get("vehicle_lpr"), dict):
                            _add_lpr_block(cam_ana_ms["vehicle_lpr"])
                        if isinstance(cam_ana_ms.get("face_matching"), dict):
                            _add_fr_block(cam_ana_ms["face_matching"])
                    cam_ana_mods = cam_ana.get("modules")
                    if isinstance(cam_ana_mods, dict):
                        if isinstance(cam_ana_mods.get("vehicle_lpr"), dict):
                            _add_lpr_block(cam_ana_mods["vehicle_lpr"])
                        if isinstance(cam_ana_mods.get("face_matching"), dict):
                            _add_fr_block(cam_ana_mods["face_matching"])

    # 4. Recursive search to catch any other dictionary mapped to "vehicle_lpr" or "face_matching"
    def _walk(obj: Any) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == "vehicle_lpr" and isinstance(v, dict):
                    _add_lpr_block(v)
                elif k == "face_matching" and isinstance(v, dict):
                    _add_fr_block(v)
                _walk(v)
        elif isinstance(obj, list):
            for item in obj:
                _walk(item)

    _walk(data)

    removed: list[tuple[str, Any]] = []

    # Sanitize LPR blocks
    lpr_keys = ("detector_weights", "reader_weights")
    for block in lpr_blocks:
        for k in lpr_keys:
            if k in block:
                old_val = block.pop(k)
                removed.append((k, old_val))
                if verbose:
                    print(f"  [OK] removed {k} ({old_val}) -> frozen default models\\lpr\\...")
                    val_str = str(old_val).replace("\\", "/")
                    is_under_anpr = val_str.lower().startswith("e:/anpr")
                    is_default_runs = val_str.startswith("runs/") or "/runs/" in val_str or val_str.startswith("./runs/")
                    if not (is_under_anpr or is_default_runs):
                        print(f"  [WARNING] Bundled weights may differ from what config asked for ({k}: {old_val})")

    # Sanitize Face Matching blocks
    fr_keys = ("yunet_weights", "sface_weights")
    for block in fr_blocks:
        for k in fr_keys:
            if k in block:
                old_val = block.pop(k)
                removed.append((k, old_val))
                if verbose:
                    print(f"  [OK] removed {k} ({old_val}) -> frozen default models\\face\\...")

    if removed:
        with open(cfg_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    return removed


# Backward-compatibility alias so existing scripts and tests pass
sanitize_lpr_weight_paths = sanitize_weight_paths


def should_sanitize_weights(with_lpr: bool = False, with_fr: bool = False) -> bool:
    """Determine whether configuration weight paths should be sanitized during build."""
    return bool(with_lpr or with_fr)


def generate_launcher_content(with_lpr: bool = False, with_fr: bool = False) -> str:
    """Generate the batch script content for the standalone live viewer launcher."""
    lpr_env_lines = ""
    if with_lpr:
        lpr_env_lines = """:: ANPR Model Environment Variables
set "ANPR_DETECTOR_WEIGHTS=%~dp0models\\lpr\\best.pt"
set "ANPR_READER_WEIGHTS=%~dp0models\\lpr\\last.pt"
"""

    fr_env_lines = ""
    if with_fr:
        fr_env_lines = """:: Face Recognition Model Environment Variables
set "FACE_DETECTOR_WEIGHTS=%~dp0models\\face\\face_detection_yunet_2023mar.onnx"
set "FACE_RECOGNIZER_WEIGHTS=%~dp0models\\face\\face_recognition_sface_2021dec.onnx"
set "FACE_MATCH_GALLERY=%~dp0data\\faces"
"""

    return f"""@echo off
setlocal
title CCTV Analytics - Live Viewer

:: Navigate to this folder
cd /d "%~dp0"

echo ===============================================================================
echo                CCTV ANALYTICS AI ENGINE - LIVE VIEWER
echo ===============================================================================
echo.

if not exist "AIEngine.exe" (
    echo [ERROR] AIEngine.exe was not found in this folder!
    echo.
    pause
    exit /b 1
)

if not exist "configs\\standalone.json" (
    echo [ERROR] configs\\standalone.json was not found!
    echo.
    pause
    exit /b 1
)

{lpr_env_lines}{fr_env_lines}echo [+] Starting CCTV Analytics Standalone Engine...
echo [TIP] Press 'q' or 'ESC' on any camera window to close the viewer.
echo.

:: Sync external user config into _internal\\configs so internal lookups also use it
if exist "_internal\\configs\\" (
    copy /Y "configs\\standalone.json" "_internal\\configs\\standalone.json" >nul
)

AIEngine.exe --standalone --config-file "%~dp0configs\\standalone.json"

if %ERRORLEVEL% neq 0 (
    echo.
    echo ===============================================================================
    echo [!] The AI Engine exited with an error. Code: %ERRORLEVEL%
    echo Please review the messages above to check your camera RTSP or config.
    echo ===============================================================================
    echo.
    pause
) else (
    echo.
    echo [OK] AI Engine closed cleanly.
)
"""


def build_executable(
    with_lpr: bool = False,
    with_fr: bool = False,
    anpr_root: Optional[str] = None,
) -> bool:
    """Execute PyInstaller build process."""
    print("==========================================================")
    print("  BUILDING STANDALONE AI ENGINE EXECUTABLE (PyInstaller)  ")
    print("==========================================================")

    fr_license_missing: bool = False
    source_standalone_file = project_root / "configs" / "standalone.json"
    source_sha_before = (
        hashlib.sha256(source_standalone_file.read_bytes()).hexdigest()
        if source_standalone_file.is_file()
        else None
    )

    if with_lpr:
        print("  LPR: included (--withLPR enabled)")
        if not anpr_root:
            anpr_root = os.environ.get("ANPR_ROOT")
        if not anpr_root:
            print("[-] Error: --withLPR requires --anpr-root or ANPR_ROOT environment variable.")
            return False

        anpr_path = Path(anpr_root).resolve()
        if not anpr_path.is_dir():
            print(f"[-] Error: ANPR root directory not found: {anpr_path}")
            return False

        anpr_v2_dir = anpr_path / "anpr_v2"
        if not anpr_v2_dir.is_dir():
            print(f"[-] Error: anpr_v2 directory not found: {anpr_v2_dir}")
            return False

        det_override = os.environ.get("ANPR_DETECTOR_WEIGHTS")
        det_weights_path = (
            Path(det_override).resolve()
            if det_override
            else anpr_path / "runs" / "detect" / "indonesian_plate_yolo26_v1" / "weights" / "best.pt"
        )

        reader_override = os.environ.get("ANPR_READER_WEIGHTS")
        reader_weights_path = (
            Path(reader_override).resolve()
            if reader_override
            else anpr_path / "runs" / "detect" / "lprd_yolo26n_320" / "weights" / "last.pt"
        )

        if not det_weights_path.is_file():
            print(f"[-] Error: Plate detector weights missing at {det_weights_path}")
            return False

        if not reader_weights_path.is_file():
            print(f"[-] Error: Plate reader weights missing at {reader_weights_path}")
            return False

        from camera_analytics.plugins.vehicle_lpr.config import VehicleLPRConfig
        reader_sha = hashlib.sha256(reader_weights_path.read_bytes()).hexdigest().upper()
        expected_sha = VehicleLPRConfig.expected_sha256.upper()
        if reader_sha != expected_sha:
            print(
                f"[-] Error: Plate reader weights SHA256 mismatch!\n"
                f"    Expected: {expected_sha}\n"
                f"    Got:      {reader_sha}"
            )
            return False

        print(f"  [OK] Validated LPR ANPR_ROOT: {anpr_path}")
        print(f"  [OK] Validated anpr_v2 directory: {anpr_v2_dir}")
        print(f"  [OK] Validated detector weights: {det_weights_path}")
        print(f"  [OK] Validated reader weights: {reader_weights_path} (SHA256: {reader_sha})")
    else:
        print("  LPR: not included (use --withLPR)")

    models_face_src = project_root / "camera_analytics" / "models" / "face"
    yunet_src = models_face_src / "face_detection_yunet_2023mar.onnx"
    sface_src = models_face_src / "face_recognition_sface_2021dec.onnx"

    if with_fr:
        print("  FR: included (--withFR enabled)")
        if not yunet_src.is_file():
            print(f"[-] Error: --withFR requires YuNet weights at {yunet_src}, but file is missing.")
            return False
        if not sface_src.is_file():
            print(f"[-] Error: --withFR requires SFace weights at {sface_src}, but file is missing.")
            return False
        print(f"  [OK] Validated YuNet weights: {yunet_src}")
        print(f"  [OK] Validated SFace weights: {sface_src}")
    else:
        print("  FR: not included (use --withFR)")

    # Read standalone.json to issue mismatch warnings
    if source_standalone_file.is_file():
        try:
            with open(source_standalone_file, "r", encoding="utf-8") as f:
                s_cfg = json.load(f)

            def _has_module(cfg: Any, mod_name: str) -> bool:
                if isinstance(cfg, dict):
                    for k, v in cfg.items():
                        if k in ("enabled_modules", "modules"):
                            if isinstance(v, (list, tuple)) and mod_name in v:
                                return True
                            if isinstance(v, dict) and mod_name in v:
                                return True
                        elif k == "cameras" and isinstance(v, list):
                            if any(_has_module(cam, mod_name) for cam in v):
                                return True
                        elif k == "analytics" and isinstance(v, dict):
                            if _has_module(v, mod_name):
                                return True
                return False

            has_lpr_in_standalone = _has_module(s_cfg, "vehicle_lpr")
            if has_lpr_in_standalone and not with_lpr:
                print("\n[WARNING] standalone.json has 'vehicle_lpr' enabled, but building WITHOUT --withLPR! Plugin execution will fail at runtime.\n")
            elif not has_lpr_in_standalone and with_lpr:
                print("\n[WARNING] Building with --withLPR, but standalone.json does not have 'vehicle_lpr' enabled in modules / enabled_modules.\n")

            has_fr_in_standalone = _has_module(s_cfg, "face_matching")
            if has_fr_in_standalone and not with_fr:
                print("\n[WARNING] standalone.json has 'face_matching' enabled, but building WITHOUT --withFR! Plugin execution will fail at runtime.\n")
            elif not has_fr_in_standalone and with_fr:
                print("\n[WARNING] Building with --withFR, but standalone.json does not have 'face_matching' enabled in modules / enabled_modules.\n")
        except Exception as warn_exc:
            print(f"[!] Warning reading standalone.json: {warn_exc}")

    spec_file = project_root / "camera_analytics" / "packaging" / "ai_engine.spec"
    cmd = [sys.executable, "-m", "PyInstaller", str(spec_file), "--noconfirm", "--clean"]

    print(f"[+] Executing Command: {' '.join(cmd)}")
    build_env = os.environ.copy()
    if with_lpr:
        build_env["AIENGINE_WITH_LPR"] = "1"
        build_env["ANPR_ROOT"] = str(anpr_path)
    if with_fr:
        build_env["AIENGINE_WITH_FR"] = "1"

    res = subprocess.run(cmd, cwd=project_root, env=build_env)
    if res.returncode != 0:
        print("[-] PyInstaller Build FAILED!")
        return False

    print("\n[+] Copying Model Files & Configuration Payload...")
    target_models_dir = dist_dir / "models"
    target_models_dir.mkdir(parents=True, exist_ok=True)

    target_configs_dir = dist_dir / "configs"
    target_configs_dir.mkdir(parents=True, exist_ok=True)

    # Copy base models
    model_sources = [
        project_root / "yolo26m-pose.pt",
        project_root / "camera_analytics" / "models" / "human" / "mivolo" / "weights" / "mivolo_v2.torchscript.pt",
        project_root / "camera_analytics" / "models" / "human" / "mivolo" / "weights" / "model.safetensors",
    ]
    for ms in model_sources:
        if ms.exists():
            shutil.copy2(ms, target_models_dir / ms.name)
            print(f"  [OK] Copied model: {ms.name} -> {target_models_dir}")

    # Copy LPR models if enabled
    if with_lpr:
        target_lpr_models_dir = target_models_dir / "lpr"
        target_lpr_models_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(det_weights_path, target_lpr_models_dir / "best.pt")
        shutil.copy2(reader_weights_path, target_lpr_models_dir / "last.pt")
        print(f"  [OK] Copied LPR models: best.pt, last.pt -> {target_lpr_models_dir}")

    # Copy Face Recognition models if enabled
    if with_fr:
        target_fr_models_dir = target_models_dir / "face"
        target_fr_models_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(yunet_src, target_fr_models_dir / yunet_src.name)
        shutil.copy2(sface_src, target_fr_models_dir / sface_src.name)

        for mf in [yunet_src, sface_src]:
            m_size = mf.stat().st_size
            m_sha = hashlib.sha256(mf.read_bytes()).hexdigest()
            print(f"  [OK] Copied FR model: {mf.name} ({m_size:,} bytes, SHA256={m_sha}) -> {target_fr_models_dir}")

        license_files = [f for f in models_face_src.iterdir() if f.is_file() and "license" in f.name.lower()]
        if license_files:
            for lf in license_files:
                shutil.copy2(lf, target_fr_models_dir / lf.name)
                print(f"  [OK] Copied FR model license: {lf.name} -> {target_fr_models_dir}")
        else:
            fr_license_missing = True
            print("  [*] Note: No LICENSE files found in camera_analytics\\models\\face\\")

        target_faces_dir = dist_dir / "data" / "faces"
        target_faces_dir.mkdir(parents=True, exist_ok=True)
        readme_path = target_faces_dir / "README.txt"
        create_faces_readme(readme_path)
        print(f"  [OK] Created empty face gallery directory with README: {readme_path}")

    # Copy configs
    config_sources = [
        project_root / "configs" / "standalone.json",
        project_root / "configs" / "distribution.manifest.json",
    ]
    for cs in config_sources:
        if cs.exists():
            shutil.copy2(cs, target_configs_dir / cs.name)
            print(f"  [OK] Copied config: {cs.name} -> {target_configs_dir}")

    # Post-build config sanitizing (when --withLPR or --withFR is set)
    if should_sanitize_weights(with_lpr=with_lpr, with_fr=with_fr):
        for cfg_dest in [
            target_configs_dir / "standalone.json",
            dist_dir / "_internal" / "configs" / "standalone.json",
        ]:
            if cfg_dest.is_file():
                sanitize_weight_paths(cfg_dest)

        if source_standalone_file.is_file() and source_sha_before:
            source_sha_after = hashlib.sha256(source_standalone_file.read_bytes()).hexdigest()
            assert source_sha_before == source_sha_after, (
                f"Source configs/standalone.json was modified during build! "
                f"({source_sha_before} != {source_sha_after})"
            )

    # Copy plugins
    target_plugins_dir = dist_dir / "camera_analytics" / "plugins"
    source_plugins_dir = project_root / "camera_analytics" / "plugins"
    if source_plugins_dir.exists():
        if target_plugins_dir.exists():
            shutil.rmtree(target_plugins_dir)
        ignore_list = get_plugin_ignore_patterns(with_lpr=with_lpr, with_fr=with_fr)
        if ignore_list:
            shutil.copytree(source_plugins_dir, target_plugins_dir, ignore=shutil.ignore_patterns(*ignore_list))
            print(f"  [OK] Copied plugins (excluding {', '.join(ignore_list)}) -> {target_plugins_dir}")
        else:
            shutil.copytree(source_plugins_dir, target_plugins_dir)
            print(f"  [OK] Copied plugins (including all plugins) -> {target_plugins_dir}")

    # Create writable runtime directories
    for wdir in ["logs", "cache", "runtime", "output", "recordings"]:
        (dist_dir / wdir).mkdir(parents=True, exist_ok=True)

    # Generate one-click launcher (run_standalone_viewer.bat)
    launcher_bat = dist_dir / "run_standalone_viewer.bat"
    launcher_content = generate_launcher_content(with_lpr=with_lpr, with_fr=with_fr)
    launcher_bat.write_text(launcher_content, encoding="utf-8")
    print(f"  [OK] Generated launcher: {launcher_bat}")

    exe_path = dist_dir / "AIEngine.exe"
    print(f"\n[+] Executable Binary Built Successfully: {exe_path}")

    # Run --verify CLI contract check on the generated executable!
    print("\n==========================================================")
    print("  RUNNING BINARY PRE-FLIGHT VERIFICATION (AIEngine --verify)")
    print("==========================================================")
    verify_env = os.environ.copy()
    if with_lpr:
        verify_env["AIENGINE_WITH_LPR"] = "1"
    if with_fr:
        verify_env["AIENGINE_WITH_FR"] = "1"

    verify_res = subprocess.run([str(exe_path), "--verify"], cwd=dist_dir, env=verify_env)
    if source_standalone_file.is_file() and source_sha_before:
        source_sha_after = hashlib.sha256(source_standalone_file.read_bytes()).hexdigest()
        assert source_sha_before == source_sha_after, (
            f"Source configs/standalone.json was modified during build! "
            f"({source_sha_before} != {source_sha_after})"
        )

    if with_fr and fr_license_missing:
        print("\n[WARNING] No LICENSE file found next to Face Recognition weights in camera_analytics\\models\\face\\.")
        print("          Bundled models: 'face_detection_yunet_2023mar.onnx' and 'face_recognition_sface_2021dec.onnx'.")
        print("          Ensure OpenCV model license terms are observed for commercial distribution.\n")

    if verify_res.returncode == 0:
        print("\n[+] AIEngine.exe --verify EXECUTABLE CONTRACT VERIFICATION PASSED!")
        return True
    else:
        print("\n[-] AIEngine.exe --verify VERIFICATION FAILED!")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PyInstaller Executable Builder for CCTV Analytics")
    parser.add_argument(
        "--withLPR",
        action="store_true",
        help="Include Vehicle LPR plugin, models, and dependencies in the build",
    )
    parser.add_argument(
        "--withFR",
        action="store_true",
        help="Include Face Recognition (YuNet + SFace) plugin, models, and dependencies in the build",
    )
    parser.add_argument(
        "--anpr-root",
        type=str,
        default=os.environ.get("ANPR_ROOT"),
        help="Path to ANPR root directory (default: ANPR_ROOT env var)",
    )
    args = parser.parse_args()

    if not build_executable(with_lpr=args.withLPR, with_fr=args.withFR, anpr_root=args.anpr_root):
        sys.exit(1)
