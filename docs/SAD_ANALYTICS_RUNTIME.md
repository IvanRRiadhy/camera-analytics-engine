# Enterprise Camera Analytics Platform — Analytics Runtime
## Software Architecture Document (SAD)

---

### Document Control
- **Document Title**: Software Architecture Document — Analytics Runtime Kernel
- **Author**: Principal Software Architect
- **Target Platform**: Enterprise Multi-Tenant Video Analytics Engine
- **Status**: APPROVED (Architecture Freeze v1.0 / Sprint 10 Architecture Blueprint)
- **Version**: 1.0.0

---

## Executive Summary & Design Rationale

System CCTV enterprise modern membutuhkan skalabilitas untuk menjalankan puluhan hingga ratusan modul analitik (seperti People Counter, Queue Monitoring, Dwell Time, Heatmap, PPE Detection, Face Recognition, ALPR, Fire/Smoke Detection, Violence Detection, Fall Detection, Forklift Tracking, ReID, dll.) di atas infrastruktur pemrosesan video tunggal atau terdistribusi.

Arsitektur tradisional yang menggabungkan logika analitik langsung ke dalam pemrosesan *frame loop* (*monolithic pipeline*) terbukti gagal pada skala enterprise akibat:
1. **Tight Coupling**: Modul analitik bergantung pada struktur internal detector/tracker.
2. **Cascading Failure**: Satu modul analitik yang bermasalah (*crash/memory leak*) dapat menghentikan seluruh pipeline kamera.
3. **Impossibility of Licensing/Hot-Swapping**: Tidak memungkinkan untuk mengaktifkan/deaktifkan modul secara dinamis sesuai lisensi tanpa menghentikan streaming kamera.

Dokumen ini mendefinisikan arsitektur **Analytics Runtime Kernel** — kernel eksekusi independen yang mengisolasi total antara *Vision Processing* dan *Business Analytics Logic* melalui kontrak **Immutable Scene**.

---

## 1. Tujuan Analytics Runtime
Tujuan utama Analytics Runtime Kernel adalah:
- Menjadi **Kernel Eksekusi Terisolasi** yang mengelola seluruh siklus hidup (*lifecycle*), pendaftaran dinamis (*plugin discovery*), dan isolasi kegagalan (*fault isolation*) dari puluhan modul analitik secara *plug-and-play*.
- Menjamin bahwa Vision Engine Core tidak pernah mengenal atau bergantung pada logika bisnis analitik mana pun.
- Menyediakan mekanisme penjadwalan (*scheduling*), manajemen memori (*memory boundaries*), isolasi thread, dan agregasi metrik/event berperforma tinggi tanpa memblokir pipeline pemrosesan video real-time.

---

## 2. Posisi Analytics Runtime di Dalam Platform
Platform dibagi menjadi tiga zona arsitektur yang terisolasi secara ketat:

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        VISION ENGINE RUNTIME                           │
│  Camera ➔ Frame Source ➔ Detector ➔ Tracker ➔ TrackManager ➔ Zone Engine│
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
                         [ Immutable Scene Snapshot ]
                                    │
┌───────────────────────────────────┴────────────────────────────────────┐
│                       ANALYTICS RUNTIME KERNEL                         │
│  Scheduler ➔ Isolation Barrier ➔ Plugin Store ➔ Context Injector       │
│  ├── Plugin A (People Counter)                                         │
│  ├── Plugin B (Loitering Detection)                                    │
│  └── Plugin C (PPE Enforcement)                                        │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
                          [ AnalyticsPayload / Entities ]
                                    │
┌───────────────────────────────────┴────────────────────────────────────┐
│                         COMMUNICATION LAYER                            │
│  Event Broadcaster ➔ Publish Queue ➔ Log / MQTT / Kafka Publishers    │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Architecture Overview
Analytics Runtime beroperasi berdasarkan prinsip **Event-Driven Reactive Processing** di atas kontrak **Immutable Scene**.

- **Inputs**: Menerima objek snapshot `Scene` (Read-Only) yang diproduksi oleh `SceneBuilder` pada setiap frame.
- **Processing**: Mengarahkan `Scene` ke modul-modul analitik terdaftar yang aktif melalui penghalang isolasi (*Isolation Barrier*) dan thread pool terisolasi.
- **Outputs**: Mengumpulkan `AnalyticsPayload` dan `StandardAnalyticsEvent` dari setiap modul analitik tanpa mengizinkan modul menulis langsung ke saluran komunikasi eksternal.

---

## 4. High Level Component Diagram

```text
                                  ┌────────────────────────┐
                                  │      Scene Layer       │
                                  └───────────┬────────────┘
                                              │ Immutable Scene
                                              ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                               ANALYTICS RUNTIME KERNEL                                 │
│                                                                                        │
│  ┌────────────────────────┐    ┌────────────────────────┐    ┌──────────────────────┐  │
│  │   Plugin Registry &    │    │    Lifecycle &         │    │  Capability &        │  │
│  │   Discovery Engine     │    │    State Controller    │    │  License Verifier    │  │
│  └───────────┬────────────┘    └───────────┬────────────┘    └───────────┬──────────┘  │
│              │                             │                             │             │
│              └─────────────────────────────┼─────────────────────────────┘             │
│                                            ▼                                           │
│  ┌──────────────────────────────────────────────────────────────────────────────────┐  │
│  │                      Runtime Scheduler & Worker Pool                             │  │
│  └─────────────────────────────────────────┬────────────────────────────────────────┘  │
│                                            │                                           │
│                 ┌──────────────────────────┼──────────────────────────┐                │
│                 ▼                          ▼                          ▼                │
│       ┌──────────────────┐       ┌──────────────────┐       ┌──────────────────┐       │
│       │ Isolation Wrapper│       │ Isolation Wrapper│       │ Isolation Wrapper│       │
│       │  (Plugin A)      │       │  (Plugin B)      │       │  (Plugin C)      │       │
│       └─────────┬────────┘       └─────────┬────────┘       └─────────┬────────┘       │
│                 │                          │                          │                │
│                 └──────────────────────────┼──────────────────────────┘                │
│                                            ▼                                           │
│  ┌──────────────────────────────────────────────────────────────────────────────────┐  │
│  │                      Event Aggregator & Result Normalizer                        │  │
│  └─────────────────────────────────────────┬────────────────────────────────────────┘  │
└────────────────────────────────────────────┼───────────────────────────────────────────┘
                                             │ Standard Events
                                             ▼
                               ┌───────────────────────────┐
                               │    Communication Layer    │
                               └───────────────────────────┘
```

---

## 5. Responsibility Setiap Komponen

1. **Plugin Registry & Discovery Engine**: Menemukan manifest plugin, memvalidasi dependensi & kompatibilitas versi, dan memuat kelas plugin secara dinamis.
2. **Lifecycle & State Controller**: Mengelola alur status plugin (`UNLOADED`, `LOADED`, `INITIALIZED`, `ACTIVE`, `PAUSED`, `STOPPED`, `ERROR`, `DISPOSED`).
3. **Capability & License Verifier**: Memeriksa lisensi aktif pelanggan dan memastikan modul analitik memiliki kapabilitas kamera/pose yang dibutuhkan sebelum diaktifkan.
4. **Runtime Scheduler & Worker Pool**: Mengatur jadwal eksekusi plugin (per-frame, interval detik, atau event-driven) serta mengalokasikan thread pemrosesan.
5. **Isolation Wrapper (Fault Barrier)**: Membungkus setiap panggilan modul analitik dalam batas exception handling, timeout watchdog, dan pengawasan memori.
6. **Event Aggregator & Result Normalizer**: Menyatukan payload hasil analisis dari berbagai modul, menormalisasi entity, dan meneruskannya ke Communication Layer.

---

## 6. Package Boundary

- `camera_analytics.runtime.kernel`: Terisolasi total dari `camera_analytics.core.pipeline` dan `camera_analytics.adapters`.
- Sub-package `camera_analytics.runtime.plugins` hanya memiliki akses ke paket `camera_analytics.scene` dan `camera_analytics.entities`.
- Dilarang keras melakukan impor sirkular (*circular import*) antara `runtime` dan `adapters`.

---

## 7. Dependency Direction

```text
[ Analytics Modules / Plugins ] ───> [ Analytics SDK / Entities / Scene ]
                                            ▲
                                            │ (Reflects Contracts Only)
                                  [ Analytics Runtime Kernel ]
                                            │
                                            ▼
                                 [ Communication Layer ]
```

---

## 8. Runtime Execution Flow

```text
1. Vision Runtime memproduksi Immutable Scene (Frame N)
2. Scene Dispatcher menerima Scene
3. Scheduler memeriksa plugin terdaftar yang AKTIF untuk Frame N
4. Scheduler mendistribusikan Scene ke Worker Threads via Isolation Wrapper
5. Plugin A, B, C mengeksekusi process(scene) secara independen
6. Isolation Wrapper menangkap AnalyticsPayload & AnalyticsEvent
7. Event Aggregator memvalidasi payload & memperbarui metrik eksekusi
8. Aggregator mengirimkan event terpadu ke Communication Layer (Publish Queue)
```

---

## 9. Lifecycle Flow & 10. Plugin Lifecycle

Setiap modul analitik wajib melewati tahapan lifecycle terstruktur:

```text
UNLOADED ➔ DISCOVERED ➔ LOADED ➔ INITIALIZED ➔ ACTIVE ──(Pause/Resume)──► PAUSED
                                      │           │
                                      ▼           ▼
                                    ERROR ◄──── STOPPED ➔ DISPOSED
```

- **UNLOADED**: File plugin berada di disk / package storage.
- **DISCOVERED**: Manifest dinilai dan divalidasi oleh Discovery Engine.
- **LOADED**: Kelas diposisikan dalam memori runtime.
- **INITIALIZED**: Konfigurasi spesifik kamera dan zona disuntikkan (*Context Injection*).
- **ACTIVE**: Modul menerima dan memproses `Scene` pada setiap siklus frame.
- **PAUSED**: Modul dihentikan sementara (lisensi habis atau kamera inactive) tanpa melepaskan konfigurasi.
- **STOPPED**: Pemrosesan dihentikan total dan buffer dibersihkan.
- **ERROR**: Modul diisolasi akibat exception berulang (*circuit breaker* dipicu).
- **DISPOSED**: Resource dilepaskan dan modul di-un-register dari runtime.

---

## 11. Plugin Discovery, 12. Registration, 13. Activation & 14. Deactivation

- **Discovery Concept**: Runtime memindai folder `/plugins` atau entry points Python `setuptools` untuk membaca `manifest.json` / `manifest.yaml` setiap modul.
- **Registration Concept**: Menggunakan pola registri terpusat dengan kunci string unik berbasis namespace (contoh: `enterprise.analytics.people_counter`).
- **Activation**: Diaktifkan berdasarkan perintah API / file konfigurasi kamera yang diverifikasi oleh `LicenseVerifier`.
- **Deactivation**: Dihentikan secara aman tanpa menggoyahkan eksekusi modul analitik lain yang sedang aktif pada kamera yang sama.

---

## 15. Module Dependency Concept & 16. Capability Negotiation

- **Module Dependency**: Modul analitik tingkat tinggi (seperti *Crowd Analytics*) dapat menetapkan dependensi terhadap keluaran modul dasar (seperti *People Counter*). Runtime menjamin modul dasar dieksekusi terlebih dahulu dalam siklus frame yang sama.
- **Capability Negotiation**: Modul menyatakan kebutuhan kapabilitas pada manifest (contoh: `requires_pose_keypoints: true`, `requires_zones: true`). Runtime mencocokkan kapabilitas ini dengan kamera/model sebelum mengizinkan aktivasi.

---

## 17. Scheduler Concept

Scheduler mengimplementasikan 3 mode eksekusi:
1. **Per-Frame Strategy (Realtime)**: Dieksekusi pada setiap frame (contoh: Intrusion / Line Crossing).
2. **Time-Sampled Strategy (Intermittent)**: Dieksekusi setiap N milidetik / N frame (contoh: Heatmap / Occupancy Density setiap 5 detik).
3. **Event-Triggered Strategy**: Hanya dieksekusi ketika terjadi peristiwa spasial tertentu (contoh: Dwell Time dieksekusi saat ada track berstatus `ENTER` zona).

---

## 18. State Management Concept

- Modul analitik bersifat **Stateful Internal, External Read-Only**.
- Status internal modul (seperti akumulator hitungan orang atau timer loitering) disimpan di dalam instance modul itu sendiri.
- Runtime menyediakan **State Storage Snapshot Barrier** untuk memungut snapshot status modul secara periodik guna kebutuhan *crash-recovery* dan migrasi multi-kamera.

---

## 19. Configuration Concept & 20. Context Injection Concept

- **Configuration Concept**: Konfigurasi berbasis hierarki JSON Schema yang divalidasi sebelum modul diinisialisasi.
- **Context Injection**: Menggunakan *Dependency Injection* terisolasi. Runtime menyuntikkan `AnalyticsContext` (konfigurasi kamera, ambang batas threshold, referensi zona) ke dalam modul pada fase `initialize()`, bukan melalui variabel global.

---

## 21. Event Aggregation & 22. Communication Boundary

- **Event Aggregation**: Menyediakan penyaringan (*deduplication*) dan agregasi berbasis jendela waktu (*windowing*) sebelum event dikirim ke saluran luar.
- **Communication Boundary**: Modul analitik **dilarang keras** membuka koneksi socket, file write, atau HTTP request mandiri. Semua keluaran berupa `AnalyticsEvent` / `AnalyticsPayload` wajib diserahkan ke Runtime Kernel untuk dikirimkan melalui Communication Layer terpusat.

---

## 23. Error Handling, 24. Fault Isolation & 25. Health Monitoring Strategy

- **Error Handling Strategy**: Menangkap seluruh unhandled exception di tingkat modul. Exception pada satu modul tidak diizinkan merambat ke *Frame Loop* utama.
- **Fault Isolation (Circuit Breaker Pattern)**:
  - Setiap modul dipantau jumlah kegagalannya.
  - Jika modul melempar exception lebih dari 5 kali berturut-turut dalam 10 detik, *Circuit Breaker* membuka dan merubah status modul menjadi `ERROR`. Modul dilewati (*bypassed*) tanpa mengganggu modul lain.
- **Health Monitoring Strategy**: Runtime memantau metrik kesehatan setiap plugin (`is_healthy`, `error_rate`, `execution_latency_ms`, `memory_growth`).

---

## 26. Metrics Collection, 27. Logging & 28. Diagnostics Strategy

- **Metrics Collection**: Mengumpulkan metrik eksekusi Prometheus-compatible (Execution Time, Event Count, Crash Count per Plugin).
- **Logging Strategy**: Log terstruktur (JSON format) dengan tag terisolasi `[plugin_id][camera_id]`.
- **Diagnostics Strategy**: Menyediakan endpoint inspeksi runtime untuk memantau status kesehatan seluruh plugin secara real-time.

---

## 29. Performance, 30. Memory Management & 31. Threading Model

- **Performance**: Pemrosesan modul analitik menggunakan arsitektur *non-blocking*. Panggilan `process(scene)` harus selesai di bawah ambang batas $15\text{ ms}$ per frame.
- **Memory Management**: Menggunakan objek `Scene` immutable berukuran konstan. Tidak ada alokasi buffer gambar baru di dalam modul analitik.
- **Threading Model**:
  - **Thread-per-Camera Worker Pool**: Setiap kamera dikelola oleh dedicated worker thread yang mengeksekusi modul-modul analitik secara sekuensial atau paralel terikat.
  - **Asynchronous Event Publishing**: Penyerahan event menggunakan *bounded queue* asynchronous.

---

## 32. Concurrency, 33. Scalability, 34. Future Distributed Runtime & 35. Multi Camera Runtime

- **Concurrency**: Eksekusi antar modul pada `Scene` yang sama bersifat konkurasi murni (karena `Scene` bersifat read-only dan bebas dari data race).
- **Scalability**: *Horizontal Pod Autoscaling* berbasis jumlah stream kamera.
- **Future Distributed Runtime**: Runtime dirancang agar dapat membedah eksekusi modul analitik ke worker node terpisah melalui gRPC / ZeroMQ di mana `Scene` diserialisasi secara kompak.
- **Future Multi Camera Runtime**: Mendukung agregasi `Scene` dari beberapa kamera (*Multi-Camera Scene Graph*) untuk fitur Cross-Camera ReID dan Global Tracking.

---

## 36. Future Cloud, 37. Future GPU Scheduling & 38. Future Licensing Architecture

- **Future Cloud**: Kemampuan hybrid edge-cloud processing di mana pemrosesan Vision Runtime berjalan di Edge device dan Analytics Runtime berjalan di Cloud.
- **Future GPU Scheduling**: Manajemen antrean inferensi GPU terpusat untuk modul-modul analitik berbasis AI sekunder (seperti Face Recognition / ALPR / Attribute ReID).
- **Future Licensing Architecture**: Lisensi terenkripsi bertingkat berbasis fitur (Feature Flags), kapasitas jumlah kamera, dan batasan tanggal kadaluarsa modul.

---

## 39. Extension Points, 40. Version Compatibility & 41. Backward Compatibility Strategy

- **Extension Points**: Mendaftarkan custom evaluator, custom payload sub-builder, dan custom event filters.
- **Version Compatibility**: SemVer (*Semantic Versioning*) pada objek `Scene` dan `AnalyticsSDK`.
- **Backward Compatibility**: Garansi kompatibilitas mundur antarmuka SDK (v1.x.x) sehingga plugin yang ditulis pada v1.0.0 tetap dapat berjalan pada v1.9.0 tanpa kompilasi ulang.

---

## 42. Plugin Manifest Concept & 43. Plugin Metadata

Manifest plugin (`manifest.yaml`) berisi skema tegas:
```yaml
id: "enterprise.analytics.loitering"
name: "Loitering Detection Module"
version: "1.2.0"
author: "Enterprise AI Team"
sdk_version: ">=1.0.0,<2.0.0"
capabilities_required:
  - "zones"
  - "track_history"
parameters_schema:
  dwell_time_seconds:
    type: "integer"
    default: 30
```

---

## 44. Security Boundary & 45. Dependency Injection Boundary

- **Security Boundary**: Modul analitik berjalan di dalam sandbox memori terbatas, dilarang melakukan impor modul sistem berbahaya (`os.system`, `subprocess`, `socket`, `eval`).
- **Dependency Injection Boundary**: Modul hanya boleh menerima dependency yang secara eksplisit disuntikkan oleh `AnalyticsContext`.

---

## 46. Recommended Folder, 47. Layer & 48. Package Structure

```text
camera_analytics/
├── runtime/                      # ANALYTICS RUNTIME KERNEL
│   ├── __init__.py
│   ├── kernel.py                 # Core Analytics Engine Kernel
│   ├── scheduler.py              # Multi-Strategy Task Scheduler
│   ├── lifecycle.py              # Plugin Lifecycle Controller
│   ├── discovery.py              # Dynamic Plugin Discovery & Loader
│   ├── registry.py               # Plugin Registry Store
│   ├── isolation.py              # Circuit Breaker & Fault Barrier
│   ├── context.py                # Context Injector & Scope Manager
│   ├── aggregator.py             # Event & Payload Aggregator
│   ├── metrics.py                # Prometheus Metrics Collector
│   └── license.py                # Capability & License Verifier
├── scene/                        # IMMUTABLE SCENE LAYER
│   ├── models.py
│   ├── builder.py
│   └── factory.py
├── entities/                     # DOMAIN ENTITIES & PAYLOAD SDK
│   ├── models.py
│   ├── payload.py
│   ├── factory.py
│   └── serializer.py
├── plugins/                      # ANALYTICS PLUGINS STORE (PLUG-AND-PLAY)
│   ├── base.py                   # Plugin Base Contract
│   ├── dummy/
│   ├── people_counter/
│   └── loitering/
└── docs/                         # ARCHITECTURE BLUEPRINTS
    ├── SAD_ANALYTICS_RUNTIME.md
    ├── ADR_ANALYTICS_RUNTIME.md
    └── ROADMAP_AND_RISK_REGISTER.md
```

---

## 49. Potential Design Risks & 50. Recommended Improvements

### Potential Design Risks:
1. **Over-Parallelization Overhead**: Eksekusi thread pool paralel pada modul analitik yang terlalu kecil dapat menyebabkan *thread contention overhead* yang lebih besar daripada durasi eksekusi modul itu sendiri.
2. **Memory Leak pada Custom State**: Modul analitik pihak ketiga yang menyimpan histori track tanpa batas waktu dapat menyebabkan penggelembung memori RAM (*memory bloat*).

### Recommended Improvements:
1. **Garbage Collection Policy untuk Plugin State**: Runtime secara otomatis membersihkan status track yang sudah dihapus oleh `TrackManager` dari memori modul analitik.
2. **Sequential Batch Execution Pattern**: Untuk modul analitik ringan, gunakan eksekusi sekuensial berantai di dalam satu worker thread per kamera guna meminimalisasi *context switching cost*.
