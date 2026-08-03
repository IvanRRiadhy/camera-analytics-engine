# Dokumentasi Kapabilitas & Fitur AI Engine v1.3.0

Dokumen ini menjelaskan seluruh fitur, kapabilitas deteksi, analisis spasial zona, estimasi pose tubuh, serta arsitektur runtime AI Engine **Enterprise CCTV Analytics Platform**.

---

## 1. Fitur Utama AI Engine

### 1.1 Object Detection & COCO 17-Point Pose Estimation
Engine menggunakan adapter **YOLO-Pose** (seperti `yolo26m-pose.pt` / `yolov8n-pose.pt` terakselerasi CUDA GPU) untuk mendeteksi manusia secara real-time dan mengekstrak **17 Titik Keypoint Pose (Kerangka Tubuh)** sesuai standar COCO:

| Keypoint Index | Bagian Tubuh | Keypoint Index | Bagian Tubuh |
|---|---|---|---|
| `0` | Hidung (*Nose*) | `9` | Pergelangan Tangan Kiri (*Left Wrist*) |
| `1` | Mata Kiri (*Left Eye*) | `10` | Pergelangan Tangan Kanan (*Right Wrist*) |
| `2` | Mata Kanan (*Right Eye*) | `11` | Pinggul Kiri (*Left Hip*) |
| `3` | Telinga Kiri (*Left Ear*) | `12` | Pinggul Kanan (*Right Hip*) |
| `4` | Telinga Kanan (*Right Ear*) | `13` | Lutut Kiri (*Left Knee*) |
| `5` | Bahu Kiri (*Left Shoulder*) | `14` | Lutut Kanan (*Right Knee*) |
| `6` | Bahu Kanan (*Right Shoulder*) | `15` | Pergelangan Kaki Kiri (*Left Ankle*) |
| `7` | Siku Kiri (*Left Elbow*) | `16` | Pergelangan Kaki Kanan (*Right Ankle*) |
| `8` | Siku Kanan (*Right Elbow*) | | |

#### Estimasi Kontak Tanah (*Ground Point Estimation*)
Untuk akurasi deteksi keberadaan manusia di dalam zona 2D kamera CCTV (yang sering memiliki distorsi perspektif), Engine tidak hanya mengandalkan titik tengah Bounding Box, tetapi menghitung **Ground Point** (titik kontak kaki dengan lantai) secara bertingkat (*fallback hierarchy*):
1. **ANKLE**: Rata-rata koordinat pergelangan kaki (`Left Ankle` + `Right Ankle`) jika visibilitas $\ge 0.5$.
2. **KNEE**: Rata-rata koordinat lutut (`Left Knee` + `Right Knee`) jika pergelangan kaki terhalang.
3. **HIP**: Rata-rata pinggul jika bagian bawah terhalang.
4. **BBOX**: Titik tengah bawah Bounding Box `(x_center, y2)` sebagai fallback terakhir.

---

### 1.2 Spatial Zone Engine (Zona & Area Kamera)

Engine mendukung pendefinisian area/zona spasial (*Region of Interest / ROI*) pada setiap kamera CCTV untuk analisis lokasi objek.

#### Tipe Zona (`ZoneType`)
- **`REGION`**: Area poligon multi-vertex (misalnya: *Restricted Area*, *Lobby Area*, *Dwell Zone*).
- **`LINE`**: Garis penyebaran untuk menghitung garis penyeberangan (*Line Crossing Counting*).
- **`FULL_FRAME`**: Seluruh area frame kamera.

#### Logika Penentuan Objek di Dalam Zona (`Ray-Casting Algorithm`)
Engine mengevaluasi posisi objek terhadap poligon zona menggunakan **Ray-Casting Containment Algorithm**:
- Penentuan titik instan: `zone.contains_point(x, y)`
- Penentuan Bounding Box: `zone.contains_bbox(bbox)`
- Evaluasi Rasio Overlap: `zone.contains_bbox_overlap(bbox, min_ratio=0.5)`

#### State Spasial Lacak Objek (`ZoneState`)
Setiap objek terdeteksi yang melintasi zona dipetakan ke dalam status spasial:
- **`OUTSIDE`**: Objek berada di luar zona.
- **`ENTER`**: Objek baru pertama kali memasuki zona pada frame ini.
- **`INSIDE`**: Objek sedang berada/berdiam di dalam zona (*Dwell Time Tracking*).
- **`EXIT`**: Objek keluar dari zona.

---

### 1.3 Object Tracking (BoT-SORT & Feature Store)

- **BoT-SORT Adapter**: Mengasosiasikan deteksi antar-frame menggunakan Kalman Filter, posisi Bounding Box, dan re-identification fitur.
- **Track Features**: Melacak `track_id`, usia lacak (*age*), kecepatan gerak (*velocity vector* $\mathbf{v} = (v_x, v_y)$), serta arah pergerakan (*cardinal direction* `N`, `NE`, `E`, `SE`, `S`, `SW`, `W`, `NW`).

---

### 1.4 Modul Analitik Modular (`Analytics Module SDK`)

- **`PeopleAnalytics`**: Modul analitik bawaan yang secara otomatis menghitung jumlah kerumunan (*Crowd Detection*), penghitungan jumlah orang per-zona (*Zone People Count*), serta mendedikasikan event alert jika kerumunan melebihi ambang batas.
- **Plugin Architecture**: Modul analitik terisolasi sepenuhnya dalam folder `plugins/` dan didaftarkan melalui `manifest.json`.

---

## 2. Arsitektur Engine & Subsystem Baseline (Sprint 11.1 – 11.3)

```text
 ┌──────────────────────────────────────────────────────────────────────────┐
 │                    Configuration & Engine Bootstrap (v1.1)               │
 │   - ConfigurationSnapshot (JSON Schema Versioning: engine, cameras, etc) │
 │   - EngineContext & ServiceRegistry (Lightweight Dependency Locator)     │
 └──────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
 ┌──────────────────────────────────────────────────────────────────────────┐
 │                 Orchestration & Catalog Layer (v1.2)                    │
 │   - CameraCatalog (Central Domain Camera Repository)                     │
 │   - SessionManager (CameraSessionState: CONNECTING, READY, RUNNING, etc) │
 │   - PipelineRegistry & PipelineCoordinator (Multi-Camera Facade)        │
 └──────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
 ┌──────────────────────────────────────────────────────────────────────────┐
 │                    Video Ingestion Layer (v1.3)                            │
 │   - VideoSource (RTSPSource, VideoFileSource)                            │
 │   - VideoDecoder (OpenCVDecoder, NVDEC/FFmpeg ready)                     │
 │   - FrameBuffer (Ring Buffer Cache for UI/Viewer)                        │
 │   - FrameQueue (Producer-Consumer Queue for AI Pipeline)                 │
 └──────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
 ┌──────────────────────────────────────────────────────────────────────────┐
 │                     AI Inference & Detection Layer                       │
 │   - DetectorPort (YOLOPoseAdapter CUDA / FakeDetector)                   │
 │   - TrackerPort (BoTSORTAdapter / FakeTracker)                           │
 │   - ZoneEngine (Polygonal Spatial Ray-Casting & Ground Point Mapping)    │
 └──────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
 ┌──────────────────────────────────────────────────────────────────────────┐
 │                  Analytics Runtime Kernel (FROZEN Core)                  │
 │   - Immutable Scene Snapshot (Read-Only to Modules)                      │
 │   - ExecutionScheduler (EVERY_FRAME, INTERVAL)                           │
 │   - CapabilityNegotiator & Exception Isolation Barrier                   │
 └──────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
 ┌──────────────────────────────────────────────────────────────────────────┐
 │                    Communication & Output Layer                          │
 │   - OutputProvider (HumanConsole, EnterpriseEvent)                       │
 │   - CommunicationManager (Thread-safe Queue & Event Serializer)          │
 │   - RabbitMQPublisher (AMQP Topic JSON Events to .NET Backend Host)      │
 └──────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Cara Menjalankan Engine & Tool Testing

### 3.1 Menjalankan Pengujian Deteksi Sederhana pada Video Rekaman
Untuk menguji Video Ingestion Layer + YOLO-Pose secara langsung pada video rekaman:
```bash
python -m camera_analytics.tools.run_simple_detection_test
```
*Output*: Hasil video deteksi dirender ke `camera_analytics/samples/output_simple_detection.mp4`.

### 3.2 Menjalankan Engine Bootstrap & Multi-Camera Validation
Untuk memverifikasi startup `EngineBootstrap`, `ConfigurationSnapshot`, `CameraCatalog`, dan `PipelineCoordinator`:
```bash
python -m camera_analytics.tools.validate_bootstrap
python -m camera_analytics.tools.validate_orchestration
python -m camera_analytics.tools.validate_ingestion
```

### 3.3 Menjalankan Registrasi Engine ke .NET Enterprise Backend
Untuk mengirimkan pesan AMQP `EngineRegistrationRequest` ke RabbitMQ broker:
```bash
python -m camera_analytics.tools.register_engine
```
