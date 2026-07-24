# Platform Developer Guide v1.0.0

---

## 1. Quick Development Setup

Platform ini dikembangkan menggunakan **Python 3.11+**, PyTorch (CUDA GPU), Ultralytics YOLO-Pose, OpenCV, dan Paho-MQTT.

### Menjalankan Unit Tests:
```bash
python -m unittest discover camera_analytics/tests
```

### Menjalankan CLI Tools Validasi Pipeline:
```bash
python -m camera_analytics.tools.validate_runtime_diagnostics
```

---

## 2. Struktur Kode Platform

- `camera_analytics/sdk/`: Public SDK interface (`AnalyticsModule`, `AnalyticsResult`, `AnalyticsEvent`).
- `camera_analytics/scene/`: Immutable domain snapshot (`Scene`, `SceneFrame`, `SceneTrack`, `SceneZone`).
- `camera_analytics/registry/`: Toko deskriptor & manajer modul (`ModuleDescriptor`, `ModuleRegistry`, `ModuleManager`).
- `camera_analytics/capability/`: Kontrak kapabilitas (`Capability`, `CapabilitySet`, `CapabilityNegotiator`).
- `camera_analytics/scheduler/`: Penjadwal timing eksekusi (`ExecutionMode`, `ExecutionPolicy`, `ExecutionScheduler`).
- `camera_analytics/discovery/`: Pemindai manifest JSON (`PluginManifest`, `ManifestLoader`, `PluginDiscovery`).
- `camera_analytics/loader/`: Dynamic import & reflection (`PluginLoader`, `PluginLoadingReport`).
- `camera_analytics/diagnostics/`: Profiling latensi & kesehatan pasif (`DiagnosticsCollector`, `DiagnosticsReport`).
- `camera_analytics/runtime/`: Kernel eksekusi terpusat (`AnalyticsRuntime`, `ExecutionEngine`, `LifecycleManager`).
