# Implementation Roadmap & Risk Register
## Enterprise Camera Analytics Platform — Analytics Runtime

---

## Part 1: Phased Implementation Roadmap

ROADMAP ini membagi pembangunan Analytics Runtime Kernel ke dalam fase-fase terstruktur untuk sprint berikutnya.

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│ FASE 1: Core Kernel & Plugin Isolation Barrier                              │
│ - Implementasi Runtime Kernel, Plugin Registry & Isolation Wrapper          │
│ - Pengujian Circuit Breaker Pattern & Fault Isolation                       │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ FASE 2: Lifecycle Controller & Dynamic Plugin Discovery                     │
│ - Implementasi Dynamic Manifest Loader & Capability Verifier                │
│ - Implementasi State Machine (LOADED, ACTIVE, PAUSED, ERROR, DISPOSED)       │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ FASE 3: Multi-Strategy Scheduler & Event Aggregator                         │
│ - Implementasi Realtime, Time-Sampled, dan Event-Triggered Scheduler        │
│ - Implementasi Event Aggregator & Metric Prometheus Collector               │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ FASE 4: Production Analytics Modules Migration & Validation                 │
│ - Migrasi modul People Counter, Dwell Time, Loitering, PPE ke Analytics SDK │
│ - Validasi Performa & Benchmark Multi-Camera Stream                         │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Part 2: Enterprise Risk Register

| Risk ID | Deskripsi Risiko | Tingkat Dampak | Probabilitas | Mitigasi Arsitektur |
|---|---|---|---|---|
| **RISK-01** | **Memory Leak pada Stateful Plugin**: Plugin analitik menyimpan histori data tanpa batas waktu, menyebabkan kemacetan RAM server. | **HIGH** | **MEDIUM** | Mengimplementasikan *Automatic State Garbage Collection* pada Kernel yang membersihkan histori track terhapus secara periodik. |
| **RISK-02** | **Thread Contention pada Over-Parallelization**: Eksekusi thread pool paralel pada modul-modul kecil menyebabkan overhead context switching melebihi durasi komputasi modul. | **MEDIUM** | **HIGH** | Menggunakan arsitektur *Hybrid Scheduler*: Sekuensial berantai di dalam satu worker thread per kamera untuk modul ringan, dan async thread pool untuk modul berat. |
| **RISK-03** | **Un-handled Crash pada External C-Library Plugin**: Plugin yang menggunakan library C/C++ eksternal mengalami Segmentation Fault yang menghentikan Python Process. | **CRITICAL** | **LOW** | Menjalankan plugin C/C++ berisiko tinggi di dalam *Subprocess Worker Boundary* terpisah dengan IPC shared memory. |
| **RISK-04** | **Bypass Isolation via Direct Network Calls**: Pengembang plugin pihak ketiga membuka koneksi HTTP/Socket langsung di dalam `process(scene)`. | **HIGH** | **MEDIUM** | Menggunakan *Security Sandbox Barrier* dan auditing static analysis yang mendeteksi serta memblokir impor modul jaringan terlarang. |
| **RISK-05** | **Inkompatibilitas Versi SDK saat Update Framework**: Pembaruan framework utama merusak modul-modul analitik versi lama. | **HIGH** | **MEDIUM** | Enforce *Semantic Versioning (SemVer)* pada `AnalyticsSDK` dan verifikasi kompatibilitas versi pada saat `Plugin Discovery`. |
