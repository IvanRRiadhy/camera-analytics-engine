# Architecture Specification — AI Engine Platform v2.0.0 (Enterprise & Standalone Edition)

**Last Updated**: October 27, 2026

---

## 1. End-to-End System Architecture

```text
                               ┌────────────────────────────────────────┐
                               │     Video Sources (RTSP / Webcam /     │
                               │          MP4 Forensic File)            │
                               └──────────────────┬─────────────────────┘
                                                  │
                                                  ▼
                               ┌────────────────────────────────────────┐
                               │   ReaderWorker & Circular FrameQueue   │
                               │     (Auto-Reconnect & Drop-Oldest)     │
                               └──────────────────┬─────────────────────┘
                                                  │
                                                  ▼
                               ┌────────────────────────────────────────┐
                               │   Detector Adapter (YOLO-Pose / CUDA)  │
                               └──────────────────┬─────────────────────┘
                                                  │
                                                  ▼
                               ┌────────────────────────────────────────┐
                               │   Tracker Adapter (BoT-SORT / ReID)    │
                               └──────────────────┬─────────────────────┘
                                                  │
                                                  ▼
                               ┌────────────────────────────────────────┐
                               │   Human Runtime & MiVOLO Demographics  │
                               │  (ROI Extraction, Age/Gender & EMA)    │
                               └──────────────────┬─────────────────────┘
                                                  │
                                                  ▼
                               ┌────────────────────────────────────────┐
                               │     ZoneEngine Spatial Evaluation      │
                               │   (Ray-Casting PIP & Line Crossing)    │
                               └──────────────────┬─────────────────────┘
                                                  │
                                                  ▼
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                             AnalyticsRuntime & Plugin Kernel                             │
│                                                                                          │
│  ┌───────────────────────┐  ┌────────────────────────┐  ┌─────────────────────────────┐  │
│  │    PluginManager      │  │   HumanState & Track   │  │     ExecutionScheduler      │  │
│  │ (People/Queue/LPR/..) │  │   Lifecycle Manager    │  │ (Priority & Stride Gating)  │  │
│  └───────────┬───────────┘  └───────────┬────────────┘  └──────────────┬──────────────┘  │
└──────────────┼──────────────────────────┼──────────────────────────────┼─────────────────┘
               │                          │                              │
               └──────────────────────────┼──────────────────────────────┘
                                          │
                 ┌────────────────────────┼────────────────────────┐
                 ▼                        ▼                        ▼
┌────────────────────────────────┐ ┌──────────────────────┐ ┌──────────────────────────────┐
│   Live Stream Viewer & Studio  │ │   SnapshotPublisher  │ │     Communication Layer      │
│  - FramePresentationBuilder    │ │  (1Hz Health/Counts  │ │  - RabbitMQPublisher (AMQP)  │
│  - Engine Development Studio   │ │   Change Detection)  │ │  - Console & NDJSON Loggers  │
│    (6 Live Inspector Panels)   │ └──────────┬───────────┘ └──────────────┬───────────────┘
└────────────────────────────────┘            │                            │
                                              └──────────────┬─────────────┘
                                                             ▼
                                              ┌──────────────────────────────┐
                                              │   ASP.NET Core Backend API   │
                                              │  (RabbitMQ / SignalR / S3)   │
                                              └──────────────────────────────┘
```

---

## 2. Core Architectural Pillars

1. **Dual Runtime Modes (`Enterprise` & `Standalone`)**:
   - **Enterprise Mode**: Connects to the ASP.NET Core Backend and RabbitMQ broker (`cctv_vhost`) for centralized configuration, heartbeat telemetry, and real-time analytics event publishing.
   - **Standalone Mode (`--standalone`)**: Operates completely offline from local JSON configuration (`configs/standalone.json`) with console/rotating file publishers and OpenCV live stream + Studio GUI windows.
2. **Environment-Aware Resource Resolution (`RuntimeResourceManager`)**:
   - Unified path resolution across Python source execution, Docker containers, and frozen PyInstaller executables (`dist/AIEngine/AIEngine.exe`), prioritizing user-editable external configs (`configs/standalone.json`) over bundled `_internal` defaults.
3. **Multi-Threaded Decoupled Ingestion & Inference**:
   - Dedicated `ReaderWorker` threads per camera stream feed bounded `FrameQueue` buffers, isolating network RTSP jitter from GPU inference workers (`PipelineExecutionWorker`).
   - Supports RTSP (`RTSPSource`), USB/UVC webcams (`WebcamSource`), and offline video files (`VideoFileSource`).
4. **Human Analytics Runtime & MiVOLO Demographics (`core/human/`)**:
   - Extracts person, face, and head ROIs from YOLO-Pose keypoints, evaluates face quality/visibility gates, and executes MiVOLO v2 (PyTorch / TorchScript) for age regression and gender classification with exponential moving average (EMA) stabilization.
5. **AI Engine Development Studio (`studio/`)**:
   - Built-in real-time observability GUI (`AI Engine Development Studio`) with 6 interactive inspector panels:
     1. *Runtime Overview*
     2. *AI Model Inspector*
     3. *Human Runtime (Track Explorer)*
     4. *Camera Inspector*
     5. *Module Inspector*
     6. *Event Timeline & Pipeline Graph*
6. **Dynamic Plugin Framework (`plugins/`)**:
   - Pluggable analytics modules including `people_counting`, `queue_detection`, `loitering_detection`, `zone_occupancy`, `crowd_detection`, and `vehicle_lpr`.
7. **Multi-Target Packaging (`packaging/`, `docker/`)**:
   - Automated PyInstaller Windows standalone executable builder (`build_executable.py`) and multi-architecture Docker builders (`windows-release`, `linux-release`, `jetson-orin`, `docker-windows`).

---

## 3. Reference Documents in `docs/`

- [`STANDALONE_EXECUTABLE_BUILD_TUTORIAL.md`](./STANDALONE_EXECUTABLE_BUILD_TUTORIAL.md) — Step-by-step guide to building `dist/AIEngine/AIEngine.exe` and `run_standalone_viewer.bat`.
- [`STANDALONE_CONFIGURATION_TUTORIAL.md`](./STANDALONE_CONFIGURATION_TUTORIAL.md) — Guide to configuring `configs/standalone.json`.
- [`BLUEPRINT_AI_ENGINE.md`](./BLUEPRINT_AI_ENGINE.md) — AI Engine & model pipeline architectural blueprint.
- [`ENGINE_TECHNICAL_REFERENCE.md`](./ENGINE_TECHNICAL_REFERENCE.md) — Exhaustive subsystem technical reference.
- [`FEATURE_FACE_MATCH_SPECIFICATION.md`](./FEATURE_FACE_MATCH_SPECIFICATION.md) — Face matching & human identity specification.
