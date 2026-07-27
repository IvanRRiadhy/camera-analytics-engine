# Platform Developer Guide v1.1.0

---

## 1. Quick Development Setup

Platform AI Engine dikembangkan menggunakan **Python 3.11+**, PyTorch (CUDA GPU), Ultralytics YOLO-Pose, OpenCV, `pika` (RabbitMQ AMQP), dan `paho-mqtt`.

### Prerequisites Installation:
```bash
pip install pika paho-mqtt torch torchvision ultralytics opencv-python
```

### Menjalankan Unit Tests:
```bash
python -m unittest discover camera_analytics/tests
```

### Menjalankan CLI Tools Validasi Pipeline & Runtime:
```bash
# Validasi Runtime Diagnostics & Profiling
python -m camera_analytics.tools.validate_runtime_diagnostics

# Validasi Registration AI Engine ke .NET Backend via RabbitMQ
python -m camera_analytics.tools.register_engine
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
- `camera_analytics/communication/`: Layer komunikasi berkecepatan tinggi (`EventPublisher`, `PublisherRegistry`, `RabbitMQPublisher`, `MQTTEventPublisher`).
- `camera_analytics/tools/`: Utility CLI untuk registrasi engine, benchmarking, dan validasi runtime.

---

## 3. Komunikasi & Messaging (RabbitMQ Integration)

Python AI Engine berkomunikasi dengan .NET 8 Backend via RabbitMQ AMQP topic exchange:

- **Broker Default Configuration**:
  - Host: `localhost` (atau `cctv_rabbitmq` di Docker network)
  - Port: `5672`
  - Virtual Host: `cctv_vhost`
  - Username: `cctv_admin`
  - Password: `SecureCctvPass123`
- **Exchange Registrasi**: `engine.events.exchange` (Topic, Durable)
- **Routing Key Registrasi**: `engine.register`
- **Exchange Analytics Events**: `cctv.analytics` (Topic, Durable)
- **Routing Key Events**: `analytics.event`

### Contoh Penggunaan `RabbitMQPublisher`:
```python
from camera_analytics.communication.publishers.rabbitmq_publisher import RabbitMQPublisher

publisher = RabbitMQPublisher(
    host="localhost",
    port=5672,
    vhost="cctv_vhost",
    username="cctv_admin",
    password="SecureCctvPass123"
)

publisher.start()
publisher.publish_raw(
    exchange="engine.events.exchange",
    routing_key="engine.register",
    payload_dict={
        "applicationId": "e078ee93-90c4-4b95-9651-7bf82c8a6d33",
        "nodeId": "8d657489-d7ef-51f2-88ed-92394587518d",
        "engineId": "99e20ace-2f16-4f8e-b220-bf064eb0f242",
        "hostname": "BCT",
        "ipAddress": "127.0.0.1",
        "maxPipelineCapacity": 8,
        "totalGpuMemoryMb": 24576
    }
)
publisher.stop()
```
