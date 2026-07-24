# Architecture Decision Records (ADR)
## Enterprise Camera Analytics Platform — Analytics Runtime

---

## ADR-001: Adopsi Immutable Scene sebagai Kontrak Tunggal Analytics Runtime

### Status
ACCEPTED (Architecture Freeze v1.0)

### Context
Sebelumnya, modul analitik menerima `RuntimeState` atau berinteraksi langsung dengan `TrackManager` dan `ZoneEngine`. Hal ini menyebabkan beberapa masalah serius:
1. Tight coupling antara modul analitik dengan komponen internal Vision Engine.
2. Efek samping (*side-effects*): Modul A yang mengubah atau menghapus objek track menyebabkan crash atau ketidakvalidan data pada Modul B yang dieksekusi setelahnya.
3. Sulit melakukan pengujian mandiri (*unit testing*) pada modul analitik tanpa membuat tiruan (*mock*) seluruh Vision Engine.

### Decision
Kami memutuskan untuk mewajibkan seluruh modul analitik **hanya menerima satu objek `Scene` yang bersifat `frozen` (Immutable Snapshot)**. Analytics tidak lagi diizinkan mengakses `RuntimeState`, `TrackManager`, atau `ZoneEngine`.

### Consequences
- **Positive**:
  - Modul analitik bersifat *pure function* tanpa side-effects.
  - Aman dieksekusi secara paralel pada banyak thread (*Thread-Safe by Design*).
  - Sangat mudah diuji dengan pembuatan instance `Scene` tiruan.
- **Negative / Trade-off**:
  - Diperlukan sedikit overhead memori untuk memabrikasi objek `Scene` pada setiap frame ($< 0.5\text{ ms}$).

---

## ADR-002: Circuit Breaker Pattern untuk Fault Isolation pada Plugin Analitik

### Status
ACCEPTED

### Context
Di platform enterprise yang mendukung puluhan plugin dari pihak ketiga atau pengembang berbeda, terdapat risiko plugin analitik mengalami unhandled exception, error eksekusi, atau memory leak. Pada arsitektur monolithic, kesalahan ini dapat menggagalkan pipeline streaming kamera.

### Decision
Setiap panggilan eksekusi `process(scene)` pada plugin dibungkus oleh **Isolation Wrapper** yang mengimplementasikan **Circuit Breaker Pattern**. Jika plugin gagal melempar exception sebanyak 5 kali berturut-turut dalam kurun 10 detik:
1. Circuit Breaker memutus panggilan ke plugin tersebut (`State: OPEN/ERROR`).
2. Event kegagalan dicatat ke diagnostic log.
3. Pipeline pemrosesan kamera dan modul analitik lainnya **tetap berjalan 100% normal**.

### Consequences
- **Positive**:
  - Isolasi kegagalan total (*Fault Tolerance* enterprise-grade).
  - Tidak ada cascading failure.
- **Negative / Trade-off**:
  - Membutuhkan sistem pelacakan status (*circuit status tracker*) pada Runtime Kernel.

---

## ADR-003: Larangan Akses I/O Jaringan Langsung dari Modul Analitik

### Status
ACCEPTED

### Context
Jika setiap modul analitik membuka saluran I/O mandiri (seperti HTTP Request ke server luar, SQL Connection, atau penulisan log file manual), akan terjadi kemacetan I/O (*I/O bottleneck*), penggelembung koneksi, dan ketidakmampuan untuk mengontrol format data terpadu platform.

### Decision
Modul analitik **dilarang keras** melakukan I/O langsung. Modul analitik cukup mengisi objek `AnalyticsPayload` atau menyerahkan `AnalyticsEvent` ke `AnalyticsRuntime`. Seluruh pengiriman data keluar dilakukan secara *asynchronous* dan *non-blocking* oleh `Communication Layer` terpusat.

### Consequences
- **Positive**:
  - Eksekusi analitik tetap sangat cepat ($< 15\text{ ms}$).
  - Keamanan jaringan terjamin (mencegah leak data dari plugin tak terpercaya).
- **Negative / Trade-off**:
  - Modul yang membutuhkan komunikasi kustom harus mendaftarkan custom publisher melalui Communication Layer Plugin Registry.

---

## ADR-004: Hierarchical Plugin Discovery dan Capability Negotiation

### Status
ACCEPTED

### Context
Platform harus mendukung pemasangan modul analitik secara dinamis tanpa mengompilasi ulang codebase utama (*zero rebuild deployment*).

### Decision
Mengimplementasikan **Plugin Discovery Engine** yang membaca manifest (`manifest.yaml`) dari setiap folder plugin. Discovery Engine melakukan *Capability Negotiation* untuk memverifikasi apakah kamera/model mendukung kapabilitas yang diminta oleh modul sebelum mengizinkan modul diubah ke status `ACTIVE`.

### Consequences
- **Positive**:
  - Sistem modular *plug-and-play* sejati.
  - Pengaktifan berbasis lisensi pelanggan sangat mudah diterapkan.
- **Negative / Trade-off**:
  - Membutuhkan standarisasi skema manifest dan pengujian kompatibilitas versi SDK yang ketat.
