# Platform Coding Standard & Code Freeze Rules v1.0.0

---

## 1. Code Freeze Rules (v1.0.0 Stable)

1. **No Breaking SDK Signature Changes**: Tidak diperbolehkan memutasi signature method pada `camera_analytics.sdk`.
2. **Immutable Domain Objects**: Semua properti domain `Scene` wajib bersifat read-only.
3. **Exception-Isolation Guarantee**: Semua pemanggilan ke modul eksternal WAJIB dibungkus `try/except` barrier.
4. **Strict Type Annotations**: Semua fungsi/method baru wajib menyertakan Type Hints Python 3.11+.

---

## 2. Type Hinting & Docstrings Standard

Gunakan format Google Python Docstrings dan Type Annotations lengkap:

```python
def process_scene(self, scene: Scene) -> AnalyticsResult:
    """Process an immutable Scene snapshot and emit analytics results.

    Args:
        scene: Immutable Scene domain snapshot.

    Returns:
        AnalyticsResult instance containing events and metrics.
    """
```