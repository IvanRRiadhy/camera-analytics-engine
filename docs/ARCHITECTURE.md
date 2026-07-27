# Architecture Specification — Platform v1.1.0 (Runtime & Messaging Active)

---

## 1. End-to-End System Architecture

```text
                               ┌────────────────────────────────────────┐
                               │       Video Source / Stream Input      │
                               └──────────────────┬─────────────────────┘
                                                  │
                                                  ▼
                               ┌────────────────────────────────────────┐
                               │   Detector Adapter (YOLO-Pose / CUDA)  │
                               └──────────────────┬─────────────────────┘
                                                  │
                                                  ▼
                               ┌────────────────────────────────────────┐
                               │   Tracker Adapter (BoT-SORT Fallback)  │
                               └──────────────────┬─────────────────────┘
                                                  │
                                                  ▼
                               ┌────────────────────────────────────────┐
                               │      Pipeline & TrackManager State     │
                               └──────────────────┬─────────────────────┘
                                                  │
                                                  ▼
                               ┌────────────────────────────────────────┐
                               │      ZoneEngine Spatial Evaluation     │
                               └──────────────────┬─────────────────────┘
                                                  │
                                                  ▼
                               ┌────────────────────────────────────────┐
                               │ SceneFactory (Immutable Snapshot)      │
                               └──────────────────┬─────────────────────┘
                                                  │
                                                  ▼
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                             AnalyticsRuntime Kernel (v1.0.0)                             │
│                                                                                          │
│  ┌───────────────────────┐  ┌────────────────────────┐  ┌─────────────────────────────┐  │
│  │    ModuleRegistry     │  │ RuntimeCapability      │  │      ExecutionScheduler     │  │
│  │ (Priority Ordering)   │  │ Provider & Negotiator  │  │ (EVERY_FRAME, INTERVAL, etc)│  │
│  └───────────┬───────────┘  └───────────┬────────────┘  └──────────────┬──────────────┘  │
│              │                          │                              │                 │
│              └──────────────────────────┼──────────────────────────────┘                 │
│                                         │                                                │
│                                         ▼                                                │
│  ┌────────────────────────────────────────────────────────────────────────────────────┐  │
│  │            ExecutionEngine (Priority Dispatch & Exception Isolation Barrier)        │  │
│  └──────────────────────────────────────┬─────────────────────────────────────────────┘  │
│                                         │                                                │
│                                         ▼                                                │
│  ┌────────────────────────────────────────────────────────────────────────────────────┐  │
│  │                   DiagnosticsCollector (Passive Latency & Health)                  │  │
│  └──────────────────────────────────────┬─────────────────────────────────────────────┘  │
└─────────────────────────────────────────┬────────────────────────────────────────────────┘
                                          │
                                          ▼
                               ┌────────────────────────────────────────┐
                               │     Communication Layer (Publishers)   │
                               │  ┌──────────────────────────────────┐  │
                               │  │        RabbitMQPublisher         │  │
                               │  │   (AMQP Topic / Persistent ACK)  │  │
                               │  └────────────────┬─────────────────┘  │
                               └───────────────────┼────────────────────┘
                                                   │
                                                   ▼
                               ┌────────────────────────────────────────┐
                               │     RabbitMQ Broker (cctv_vhost)       │
                               │  - engine.events.exchange (Topic)      │
                               │  - cctv.analytics (Topic)              │
                               └───────────────────┬────────────────────┘
                                                   │
                                                   ▼
                               ┌────────────────────────────────────────┐
                               │       .NET 8 Backend API Host          │
                               │  (EngineRegistrationConsumerService)   │
                               └───────────────────┬────────────────────┘
                                                   │
                                                   ▼
                               ┌────────────────────────────────────────┐
                               │    SQL Server (WorkerNodes & Instances)│
                               └────────────────────────────────────────┘
```

---

## 2. Core Architectural Pillars

1. **Immutable Domain Snapshot (`Scene`)**: Pemisahan total antara state internal pengelakan objek dan modul analitik. Modul analitik bersifat *read-only*.
2. **Plugin Architecture & Discovery**: Modul analitik ditemukan secara otomatis dari `manifest.json` di bawah `plugins/` dan dimuat secara dinamis via `PluginLoader`.
3. **Capability Negotiation**: Kernel memverifikasi kemampuan platform (`CapabilitySet`) sebelum mengeksekusi modul; modul yang tidak didukung bertransisi ke `UNSUPPORTED` secara bersih.
4. **Execution Scheduler**: Pengaturan ritme waktu eksekusi (`EVERY_FRAME`, `INTERVAL`, `MANUAL`) terpisah dari logika pemrosesan modul.
5. **Exception Isolation Barrier**: Kegagalan modul analitik diisolasi penuh tanpa merusak kernel utama.
6. **Passive Diagnostics & Profiling**: Kolektor metrik pasif tanpa efek samping pada alur eksekusi kernel.
7. **Distributed Worker Registration**: Integrasi AMQP RabbitMQ (`RabbitMQPublisher`) untuk mendaftarkan identitas node (`WorkerNode`) dan instance (`EngineInstance`) secara otomatis ke .NET Backend.