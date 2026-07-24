# Reference Analytics Plugin Template

Template resmi ini dapat disalin ke dalam direktori `plugins/` sebagai titik awal pembuatan modul analitik kustom baru.

## Cara Menggunakan Template:

1. Salin folder `reference_plugin/` ke direktori `plugins/my_new_plugin/`.
2. Edit `manifest.json`:
   - Ubah `"plugin_id"` menjadi ID unik plugin Anda (misal `"loitering_detector"`).
   - Ubah `"entry_point"` mengacu ke path kelas Python Anda.
3. Edit `module.py`:
   - Tulis logika pemrosesan analitik di dalam metode `process_scene(self, scene: Scene)`.
4. Jalankan validasi discovery:
   ```bash
   python -m camera_analytics.tools.validate_plugin_discovery
   ```
