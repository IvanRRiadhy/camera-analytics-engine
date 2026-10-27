"""
Automated PyInstaller Executable Builder for CCTV Analytics AI Engine.

Executes PyInstaller build using `ai_engine.spec`, copies required models, configs,
and plugins to `dist/AIEngine/`, and runs `--verify` validation on the generated binary.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
dist_dir = project_root / "dist" / "AIEngine"


def build_executable() -> bool:
    """Execute PyInstaller build process."""
    print("==========================================================")
    print("  BUILDING STANDALONE AI ENGINE EXECUTABLE (PyInstaller)  ")
    print("==========================================================")

    spec_file = project_root / "camera_analytics" / "packaging" / "ai_engine.spec"
    cmd = [sys.executable, "-m", "PyInstaller", str(spec_file), "--noconfirm", "--clean"]

    print(f"[+] Executing Command: {' '.join(cmd)}")
    res = subprocess.run(cmd, cwd=project_root)
    if res.returncode != 0:
        print("[-] PyInstaller Build FAILED!")
        return False

    print("\n[+] Copying Model Files & Configuration Payload...")
    target_models_dir = dist_dir / "models"
    target_models_dir.mkdir(parents=True, exist_ok=True)

    target_configs_dir = dist_dir / "configs"
    target_configs_dir.mkdir(parents=True, exist_ok=True)

    # Copy models
    model_sources = [
        project_root / "yolo26m-pose.pt",
        project_root / "camera_analytics" / "models" / "human" / "mivolo" / "weights" / "mivolo_v2.torchscript.pt",
        project_root / "camera_analytics" / "models" / "human" / "mivolo" / "weights" / "model.safetensors",
    ]
    for ms in model_sources:
        if ms.exists():
            shutil.copy2(ms, target_models_dir / ms.name)
            print(f"  [OK] Copied model: {ms.name} -> {target_models_dir}")

    # Copy configs
    config_sources = [
        project_root / "configs" / "standalone.json",
        project_root / "configs" / "distribution.manifest.json",
    ]
    for cs in config_sources:
        if cs.exists():
            shutil.copy2(cs, target_configs_dir / cs.name)
            print(f"  [OK] Copied config: {cs.name} -> {target_configs_dir}")

    # Copy plugins
    target_plugins_dir = dist_dir / "camera_analytics" / "plugins"
    source_plugins_dir = project_root / "camera_analytics" / "plugins"
    if source_plugins_dir.exists():
        if target_plugins_dir.exists():
            shutil.rmtree(target_plugins_dir)
        shutil.copytree(source_plugins_dir, target_plugins_dir)
        print(f"  [OK] Copied plugins -> {target_plugins_dir}")

    # Create writable runtime directories
    for wdir in ["logs", "cache", "runtime", "output", "recordings"]:
        (dist_dir / wdir).mkdir(parents=True, exist_ok=True)

    # Generate one-click launcher (run_standalone_viewer.bat)
    launcher_bat = dist_dir / "run_standalone_viewer.bat"
    launcher_content = """@echo off
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

echo [+] Starting CCTV Analytics Standalone Engine...
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
    launcher_bat.write_text(launcher_content, encoding="utf-8")
    print(f"  [OK] Generated launcher: {launcher_bat}")

    exe_path = dist_dir / "AIEngine.exe"
    print(f"\n[+] Executable Binary Built Successfully: {exe_path}")

    # Run --verify CLI contract check on the generated executable!
    print("\n==========================================================")
    print("  RUNNING BINARY PRE-FLIGHT VERIFICATION (AIEngine --verify)")
    print("==========================================================")
    verify_res = subprocess.run([str(exe_path), "--verify"], cwd=dist_dir)
    if verify_res.returncode == 0:
        print("\n[+] AIEngine.exe --verify EXECUTABLE CONTRACT VERIFICATION PASSED!")
        return True
    else:
        print("\n[-] AIEngine.exe --verify VERIFICATION FAILED!")
        return False


if __name__ == "__main__":
    if not build_executable():
        sys.exit(1)
