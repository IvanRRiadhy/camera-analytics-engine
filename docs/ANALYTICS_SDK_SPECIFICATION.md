# Enterprise Camera Analytics Platform — Public Analytics SDK
## Public API Architecture & Contract Specification (The Platform Constitution)

---

### Document Control
- **Document Title**: Public Analytics SDK Specification (Public API Contract & Plugin Developer Guide)
- **Author**: Principal Software Architect & Framework Designer
- **Target Platform**: Enterprise Multi-Tenant Video Analytics Platform
- **SDK Stability Scope**: Long-Term Public API (Guaranteed Backward Compatibility v1.x)
- **Status**: APPROVED ARCHITECTURAL BLUEPRINT
- **Version**: 1.0.0

---

## Executive Summary: The SDK as the Platform Constitution

Dalam pembuatan platform analitik enterprise berskala besar, **Analytics SDK** bertindak sebagai **"Konstitusi Publik Platform"**. 

- **Vision Runtime**: Bertanggung jawab memproses piksel gambar, deteksi AI, dan tracking objek untuk memproduksi `Scene`.
- **Analytics Runtime**: Bertanggung jawab mengelola thread, siklus hidup, isolasi kesalahan (*circuit breaker*), dan penjadwalan.
- **Analytics Plugin**: Pengembang aplikasi analitik pihak ketiga yang membangun modul bisnis (People Counter, PPE, Heatmap, ALPR, ReID, dll.).
- **Analytics SDK**: **Satu-satunya titik temu (Surface Boundary)** antara Plugin dan Platform.

Plugin **TIDAK BOLEH** mengetahui implementasi internal Runtime. Runtime dapat dirombak dari single-node menjadi cloud-native Kubernetes cluster, namun selama **Analytics SDK Contract** tidak berubah, seluruh puluhan plugin analitik yang telah dibangun oleh developer di seluruh dunia **dijamin akan terus berjalan tanpa recompilation / code changes**.

---

## 1. Tujuan Analytics SDK

1. **Aset Stabilitas Jangka Panjang**: Menyediakan Public API Surface yang stabil selama bertahun-tahun dengan garansi tanpa *breaking changes* pada mayor rilis yang sama (`v1.x.x`).
2. **Inversion of Control (IoC) & Loose Coupling**: Mengisolasi penuh logika bisnis analitik dari infrastruktur Vision Processing, GPU inference, dan I/O jaringan.
3. **Developer Experience (DX) Kelas Enterprise**: Memberikan pengembang plugin antarmuka bertipe kuat (*strongly-typed*), autocompletion, dan kontrak abstrak yang jelas.

---

## 2. Posisi SDK di dalam Platform Architecture

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        ANALYTICS PLUGIN STORE                          │
│   (People Counter, PPE Enforcement, Heatmap, Face Recognition, ALPR)   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼  (Consumes ONLY Public SDK)
==========================================================================
                     ANALYTICS SDK SURFACE BOUNDARY                       
==========================================================================
  ├── Contracts  : IAnalyticsModule, IModuleLifecycle, IAnalyticsContext
  ├── Models     : Scene, TrackEntity, ZoneEntity, CameraEntity, FrameEntity
  ├── Builders   : AnalyticsPayload, EventBuilder, PayloadExtensions
  └── Services   : IStateStore, IMetricCollector, ILogger, IEventPublisher
==========================================================================
                                    ▲  (Implements / Injects Infrastructure)
                                    │
┌───────────────────────────────────┴────────────────────────────────────┐
│                       ANALYTICS RUNTIME KERNEL                         │
│  Scheduler, Circuit Breaker, State Manager, Metrics Registry, Publisher│
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Architecture Overview

Arsitektur SDK mengadopsi **Hexagonal Architecture (Ports and Adapters)**:
- **Core Domain**: Objek `Scene` (Immutable) dan Domain Entities (`TrackEntity`, `ZoneEntity`, `CameraEntity`).
- **Inbound Ports**: Kontrak `IAnalyticsModule` & `IModuleLifecycle` yang wajib diimplementasikan oleh plugin.
- **Outbound Ports**: Kontrak infrastruktur (`IStateStore`, `IMetricCollector`, `ILogger`, `IEventPublisher`) yang disediakan oleh SDK dan disuntikkan (*Dependency Injection*) oleh Runtime Kernel.

---

## 4. Public API Boundary & 5. Dependency Boundary

- **Public API Boundary**: Hanya komponen di bawah namespace `camera_analytics.sdk.*` yang dianggap sebagai Public API. Segala komponen di luar namespace ini bersifat internal private platform.
- **Dependency Boundary**: Modul plugin **HANYA BOLEH** mengimpor `camera_analytics.sdk`. Dilarang keras mengimpor `camera_analytics.core`, `camera_analytics.adapters`, atau `camera_analytics.runtime`.

```text
[ Plugin Module ] ─── ALLOWED ───► [ Analytics SDK ] ◄─── IMPLEMENTS ─── [ Runtime Kernel ]
        │                                  │
        └────────────── DENIED ────────────┴─────────────► [ Core / Adapters ]
```

---

## 6. Package Boundary, 7. Layer Boundary & 39-42. Namespace & Naming

Standardisasi Namespace & Layering:
- **`camera_analytics.sdk.contracts`**: Antarmuka murni (`IAnalyticsModule`, `ILifecycle`, `IContext`).
- **`camera_analytics.sdk.models`**: Objek data immutable (`Scene`, `Entities`).
- **`camera_analytics.sdk.payload`**: SDK pembangun payload bertipe kuat (`AnalyticsPayload`).
- **`camera_analytics.sdk.services`**: Service ports (`ILogger`, `IMetricCollector`, `IStateStore`).
- **`camera_analytics.sdk.exceptions`**: Hirarki exception publik (`AnalyticsSDKException`).

---

## 8. Module Contract & 9. Module Lifecycle Contract

Setiap modul analitik wajib mematuhi antarmuka `IAnalyticsModule` dan `IModuleLifecycle`:

```text
                                  ┌──────────────────┐
                                  │   UNINITIALIZED  │
                                  └────────┬─────────┘
                                           │ initialize(context)
                                           ▼
                                  ┌──────────────────┐
                                  │    INITIALIZED   │
                                  └────────┬─────────┘
                                           │ start()
                                           ▼
                                  ┌──────────────────┐
                                  │      ACTIVE      │ ◄───► process(scene)
                                  └────────┬─────────┘
                                           │ stop()
                                           ▼
                                  ┌──────────────────┐
                                  │     STOPPED      │
                                  └────────┬─────────┘
                                           │ dispose()
                                           ▼
                                  ┌──────────────────┐
                                  │     DISPOSED     │
                                  └──────────────────┘
```

---

## 10. Analytics Context, 11. Configuration & 12. Capability Contracts

- **`IAnalyticsContext`**: Menyediakan akses ke konfigurasi modul yang disuntikkan, metadata kamera, daftar zona spasial, dan service ports (`Logger`, `StateStore`, `Metrics`).
- **`IModuleConfiguration`**: Membaca parameter konfigurasi yang divalidasi oleh skema JSON Schema.
- **`ICapabilityContract`**: Menyatakan kapabilitas yang dibutuhkan plugin (misal: `REQUIRES_POSE`, `REQUIRES_ZONES`, `REQUIRES_GLOBAL_REID`).

---

## 13. Plugin Manifest Schema & 14. Plugin Metadata

Setiap plugin menyertakan berkas `plugin.manifest.json`:
```json
{
  "plugin_id": "com.enterprise.analytics.people_counter",
  "name": "People Counting & Line Crossing Module",
  "version": "1.0.0",
  "sdk_version": ">=1.0.0,<2.0.0",
  "entry_class": "PeopleCounterModule",
  "capabilities": ["ZONES", "TRACK_HISTORY"],
  "configuration_schema": {
    "type": "object",
    "properties": {
      "count_threshold": { "type": "integer", "default": 10 }
    }
  }
}
```

---

## 15. Analytics Event, 16. Payload & 17. Analytics Result Contracts

- **`AnalyticsResult`**: Hasil kembalian dari `process(scene)` yang berisi status sukses, daftar `AnalyticsEvent` yang diproduksi, dan metrik internal eksekusi.
- **`AnalyticsPayload`**: Builder bertipe kuat yang mengeliminasi pembentukan string JSON manual oleh plugin.
- **`AnalyticsEvent`**: Dibuat melalui `EventBuilder` yang disediakan SDK.

---

## 18. State, 19. Storage & 20. Metrics Contracts

- **`IStateStore`**: Kontrak key-value terisolasi per-plugin untuk menyimpan status antar-frame tanpa khawatir kehilangan memori saat restart.
- **`IMetricCollector`**: Kontrak mendaftar counter, gauge, dan histogram metrik eksekusi (Prometheus-compatible).
- **`ILogger`**: Kontrak logging terstruktur dengan penandaan otomatis `[plugin_id][camera_id]`.

---

## 21-28. Services & Infrastructure Contracts

- **`IHealthCheck`**: Kontrak inspeksi kesehatan internal plugin (`check_health()`).
- **`IClock`**: Kontrak waktu abstrak (`now_utc()`, `now_timestamp()`) yang memungkinkan pengujian deterministik berbasis simulasi waktu.
- **`IEventPublisher`**: Kontrak pengiriman event ke saluran eksternal.

---

## 29-33. Version Compatibility & Stability Policies

- **Semantic Versioning (SemVer)**:
  - `MAJOR` (v1.0.0 ➔ v2.0.0): Breaking API Changes.
  - `MINOR` (v1.0.0 ➔ v1.1.0): Perluasan antarmuka baru tanpa merusak kode lama (*Backward Compatible*).
  - `PATCH` (v1.0.0 ➔ v1.0.1): Perbaikan bug internal SDK.
- **Deprecation Policy**: Interface yang akan dihapus wajib diberi anotasi `@deprecated` dan dipertahankan minimal selama **2 Minor Release** sebelum dihapus pada Major Release berikutnya.

---

## 34-38. Extension, Negotiation & Error Models

- **Capability Negotiation**: Runtime menolak aktivasi plugin jika kapabilitas yang diminta oleh manifest plugin tidak didukung oleh Vision Engine.
- **Error Model & Exception Hierarchy**:
  - `AnalyticsSDKException` (Base Exception)
    - `ConfigurationException`
    - `CapabilityMismatchException`
    - `InvalidPluginException`
    - `ExecutionTimeoutException`

---

## 41-43. Package & Directory Structure

```text
camera_analytics/
└── sdk/                           # PUBLIC ANALYTICS SDK (PUBLIC CONSTITUTION)
    ├── __init__.py
    ├── contracts/                 # Public Interface Ports
    │   ├── module.py
    │   ├── lifecycle.py
    │   ├── context.py
    │   ├── capability.py
    │   └── services.py
    ├── models/                    # Immutable Domain Models
    │   ├── scene.py
    │   ├── entities.py
    │   └── result.py
    ├── payload/                   # Strongly Typed Payload Builders
    │   ├── builder.py
    │   └── extensions.py
    ├── exceptions/                # Public Exception Hierarchy
    │   └── base.py
    └── testing/                   # SDK Test Harness for Plugin Developers
        ├── mock_scene.py
        └── test_runner.py
```

---

## 44-48. Developer Experience (DX), Certification & Anti-Patterns

### Anti-Patterns yang Wajib Dihindari Pengembang Plugin:
1. ❌ **Direct I/O Call Anti-Pattern**: Menggunakan `urllib`, `requests`, atau `open()` untuk menulis log ke jaringan/disk luar secara langsung.
2. ❌ **Runtime State Leak Anti-Pattern**: Mengimpor modul internal Vision Engine (`camera_analytics.core`).
3. ❌ **Global Mutable State Anti-Pattern**: Menyimpan status variabel di tingkat global Python module.
4. ❌ **Scene Mutation Attempt Anti-Pattern**: Mencoba memodifikasi tuple `scene.tracks`.

---

## 49. Design Trade-offs & Critical Audit Response

### Kritik Terhadap SAD/ADR Sebelumnya & Solusi SDK:
1. **Kritik SAD Lama (Direct Dictionary Payload)**:
   - *Masalah*: SAD sebelumnya mengizinkan modul menulis payload sebagai dictionary `dict[str, Any]`. Ini rawan *typo* dan mematahkan *Strong Typing*.
   - *Solusi SDK Baru*: Wajib menggunakan `AnalyticsPayload` SDK Builder yang bertipe kuat.
2. **Kritik SAD Lama (Asynchronous Unbounded Task Scheduling)**:
   - *Masalah*: Jika plugin membuat background thread sendiri, thread tersebut sulit dibatasi memorinya.
   - *Solusi SDK Baru*: SDK menyediakan `IScheduler` terisolasi yang dikendalikan oleh Runtime Kernel.

---

## Part 2: Phased Implementation Roadmap for Analytics SDK

Roadmap ini menentukan urutan pembuatan komponen SDK secara bertahap sebelum Runtime Kernel dibangun:

```text
Fase 1: Immutable Domain Models & Exceptions (Scene, TrackEntity, ZoneEntity, Base Exceptions)
  │  (Alasan: Objek data domain adalah fondasi utama yang dibaca oleh seluruh antarmuka SDK)
  ▼
Fase 2: Base Interface Contracts & Context (IAnalyticsModule, IModuleLifecycle, IAnalyticsContext)
  │  (Alasan: MendefinisikanPublic Surface dan pola penyuntingan Dependency Injection)
  ▼
Fase 3: Strongly Typed Payload SDK & Event Builders (AnalyticsPayload, EventBuilder, AnalyticsResult)
  │  (Alasan: Memungkinkan modul analitik mengemas hasil analisis tanpa JSON manual)
  ▼
Fase 4: Infrastructure Service Ports (ILogger, IMetricCollector, IStateStore, IClock)
  │  (Alasan: Menyediakan abstraksi I/O dan state management bagi plugin)
  ▼
Fase 5: SDK Testing Harness & Mock Suite (MockSceneBuilder, PluginTestRunner)
     (Alasan: Memungkinkan developer menguji modul analitik secara terisolasi tanpa Vision Engine)
```
