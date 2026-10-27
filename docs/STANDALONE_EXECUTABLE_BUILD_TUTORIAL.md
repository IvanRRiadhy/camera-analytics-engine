# Standalone AI Engine Executable Build Tutorial (`dist/AIEngine`)

This guide walks through every step and command required to compile the Python AI Engine source code into the standalone Windows package in `dist\AIEngine\`—complete with `AIEngine.exe`, bundled models, plugins, configuration files, and the one-click `run_standalone_viewer.bat` launcher.

---

## Prerequisites

Make sure the following files are present in your project workspace (`e:\CCTV Analytics`) before running the build:

- **Python Virtual Environment**: `.venv` (Python 3.10 / 3.11)
- **Model Weights**:
  - `yolo26m-pose.pt` (in project root)
  - `camera_analytics\models\human\mivolo\weights\mivolo_v2.torchscript.pt`
  - `camera_analytics\models\human\mivolo\weights\model.safetensors`
- **Configuration Files**:
  - `configs\standalone.json`
  - `configs\distribution.manifest.json`

---

## Step 1: Open PowerShell & Activate the Virtual Environment

Open a PowerShell terminal in the project root directory and activate `.venv`:

```powershell
cd "e:\CCTV Analytics"
.\.venv\Scripts\Activate.ps1
```

---

## Step 2: Install / Verify Build Dependencies

Ensure all runtime dependencies and `pyinstaller` are installed inside the active virtual environment:

```powershell
pip install -r requirements.txt
pip install pyinstaller
```

---

## Step 3: (Optional) Pre-Configure Default Camera Settings

During the build process, `configs\standalone.json` in the project root is copied into `dist\AIEngine\configs\standalone.json`.

- If you want specific camera RTSP URLs or polygon zones baked into the initial build output, edit `configs\standalone.json` before running Step 4.
- You can also modify `dist\AIEngine\configs\standalone.json` at any time **after** building without needing to recompile `AIEngine.exe`.

---

## Step 4: Run the Automated Executable Builder

Run the automated packaging script from the project root:

```powershell
python -m camera_analytics.packaging.build_executable
```

*(Alternatively, you can invoke the multi-target build profile runner, which executes the same Windows PyInstaller pipeline:)*

```powershell
python -m camera_analytics.packaging.build_profile --profile windows-release
```

### What This Command Does Automatically

1. **Compiles `AIEngine.exe`**: Runs `PyInstaller` using `camera_analytics\packaging\ai_engine.spec` (`--noconfirm --clean`), outputting `dist\AIEngine\AIEngine.exe` and internal runtime dependencies in `dist\AIEngine\_internal\`.
2. **Copies AI Model Weights**: Copies `yolo26m-pose.pt`, `mivolo_v2.torchscript.pt`, and `model.safetensors` into `dist\AIEngine\models\`.
3. **Copies Configurations**: Copies `configs\standalone.json` and `configs\distribution.manifest.json` into `dist\AIEngine\configs\`.
4. **Copies Analytics Plugins**: Copies `camera_analytics\plugins\` into `dist\AIEngine\camera_analytics\plugins\`.
5. **Creates Runtime Directories**: Creates writable folders (`logs\`, `cache\`, `runtime\`, `output\`, `recordings\`) inside `dist\AIEngine\`.
6. **Generates `run_standalone_viewer.bat`**: Writes the one-click launcher script at `dist\AIEngine\run_standalone_viewer.bat`.
7. **Runs Pre-Flight Verification**: Executes `dist\AIEngine\AIEngine.exe --verify` to confirm the binary initializes cleanly.

---

## Step 5: Verify & Launch the Built Package

### 1. (Optional) Run the 10-Checkpoint Self-Test

To verify that config loading, plugins, and runtime services pass all diagnostic checks on the compiled binary:

```powershell
.\dist\AIEngine\AIEngine.exe --self-test
```

### 2. Configure Your Cameras (`dist\AIEngine\configs\standalone.json`)

To change camera RTSP URLs, FPS, or detection zones after building, edit:

```text
dist\AIEngine\configs\standalone.json
```

> **Note:** You only ever need to edit `dist\AIEngine\configs\standalone.json`. When `run_standalone_viewer.bat` runs, it passes the absolute path to `dist\AIEngine\configs\standalone.json` and automatically syncs it to `dist\AIEngine\_internal\configs\standalone.json`.

### 3. Click to Run

Double-click **`dist\AIEngine\run_standalone_viewer.bat`** in File Explorer (or run it from PowerShell):

```powershell
.\dist\AIEngine\run_standalone_viewer.bat
```

- **Engine Studio Window**: Opens immediately upon startup to display live telemetry, pipeline health, and inspector tabs (`Tab` to cycle tabs).
- **Camera Stream Viewer Windows**: Open automatically as soon as each camera's RTSP/video stream connects and decodes its first frame.
- **Stop / Exit**: Press `q` or `ESC` while focused on any OpenCV window to trigger a graceful shutdown.

---

## Resulting `dist\AIEngine\` Folder Structure

```text
dist\AIEngine\
├── _internal\                      # PyInstaller bundled Python runtime & DLLs
├── cache\                          # Runtime cache directory
├── camera_analytics\
│   └── plugins\                    # Analytics plugins (people_counting, queue_detection, etc.)
├── configs\
│   ├── distribution.manifest.json  # Build manifest
│   └── standalone.json             # User-editable camera & runtime configuration
├── logs\                           # Daily engine logs & analytics.log / analytics.ndjson
├── models\                         # Bundled YOLO-Pose & MiVOLO weights
├── output\                         # Exported outputs
├── recordings\                     # Video recordings
├── runtime\                        # Runtime state files
├── AIEngine.exe                    # Compiled AI Engine executable
└── run_standalone_viewer.bat       # One-click standalone viewer launcher
```

