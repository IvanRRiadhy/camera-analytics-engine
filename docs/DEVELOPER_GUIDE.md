# AI Engine Developer Guide — Platform v2.0.0

**Last Updated**: October 27, 2026

---

## 1. Quick Development Setup

The AI Engine (`camera_analytics`) is built with **Python 3.10 / 3.11+**, PyTorch (CUDA / CPU), Ultralytics YOLO-Pose (`yolo26m-pose.pt`), MiVOLO v2 (`timm` / `safetensors` / TorchScript), OpenCV, and `pika` (RabbitMQ AMQP).

### Activate Virtual Environment & Install Dependencies
```powershell
cd "e:\CCTV Analytics"
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

---

## 2. Running the Engine

### A. Standalone Mode (Local Config + Live Viewer & Engine Studio)
```powershell
python -m camera_analytics.main --standalone --config-file configs/standalone.json
```
Or click `run_standalone_viewer.bat`.

### B. Headless Standalone Mode (No GUI Windows)
```powershell
python -m camera_analytics.main --standalone --config-file configs/standalone.json --headless
```

### C. Enterprise Mode (Connected to .NET Backend & RabbitMQ)
```powershell
python -m camera_analytics.main --mode enterprise --backend-url http://localhost:5100
```

### D. Self-Test, Pre-Flight Verification & Benchmarks
```powershell
# Pre-flight environment & distribution verification
python -m camera_analytics.main --verify

# 10-checkpoint end-to-end diagnostic self-test
python -m camera_analytics.main --self-test

# Automated runtime benchmark & HTML report generation
python -m camera_analytics.main --benchmark --report
```

---

## 3. Building the Standalone Executable (`dist/AIEngine`)

To compile the Python codebase into `dist\AIEngine\AIEngine.exe` along with bundled models, configs, plugins, and `run_standalone_viewer.bat`:

```powershell
python -m camera_analytics.packaging.build_executable
```
See [`STANDALONE_EXECUTABLE_BUILD_TUTORIAL.md`](./STANDALONE_EXECUTABLE_BUILD_TUTORIAL.md) for the full step-by-step build tutorial.

---

## 4. Running the Test Suite

```powershell
pytest camera_analytics/tests
```

---

## 5. Key Package Directory Structure

- `camera_analytics/adapters/`: Detection (`YOLOPoseAdapter`), tracking (`BoTSORTAdapter`), and pipeline execution worker bridges (`InferencePipeline`, `PipelineExecutionWorker`).
- `camera_analytics/bootstrap/`: Engine startup (`EngineBootstrap`), `StandaloneConfigurationProvider`, `RuntimeResourceManager`, and `RuntimeSelfTest`.
- `camera_analytics/communication/`: Asynchronous event & snapshot publishing (`CommunicationManager`, `RabbitMQPublisher`, `ConsolePublisher`, `LogPublisher`).
- `camera_analytics/core/human/`: Human state tracking, ROI extraction, quality gating, and MiVOLO age/gender inference runtime.
- `camera_analytics/core/spatial/`: `ZoneManager` & `ZoneEngine` ray-casting point-in-polygon spatial evaluation.
- `camera_analytics/docker/`: Multi-target Docker image and Compose package builders.
- `camera_analytics/ingestion/`: Video stream readers (`RTSPSource`, `WebcamSource`, `VideoFileSource`), `FrameQueue`, and `ReaderWorker`.
- `camera_analytics/packaging/`: PyInstaller spec (`ai_engine.spec`), `build_executable.py`, and multi-profile runner (`build_profile.py`).
- `camera_analytics/plugins/`: Modular analytics plugins (`people_counting`, `queue_detection`, `loitering_detection`, `vehicle_lpr`, etc.).
- `camera_analytics/studio/`: Live OpenCV observability UI (`StudioLauncher`, `EngineStudioCoordinator`, and 6 inspector panels).
- `camera_analytics/viewer/`: Live camera stream overlay rendering (`OverlayRenderer`, `WindowManager`, `HumanStatePresenter`).
