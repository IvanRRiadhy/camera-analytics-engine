# Vehicle LPR Plugin (`camera_analytics.plugins.vehicle_lpr`)

An enterprise analytics plugin integrating Indonesian vehicle license plate recognition (ANPR / LPR) using YOLOv26 detection and specialized character recognition with grammatical voting consensus.

---

## 1. Purpose & Architecture

The `vehicle_lpr` plugin operates inside the Camera Analytics Engine (`camera_analytics`) as a pipeline vision plugin (`BaseAnalyticsPlugin`).

### Core Design Principles:
1. **Shared Model Singleton (`SharedModelCache`)**:
   - Multiple camera pipelines share a single in-memory instance of the Plate Detector (`ultralytics.YOLO`) and Character Reader (`anpr_v2.reader.CharDetectorReader`).
   - Thread-safe reference counting loads the weights once upon first pipeline initialization and unloads models with `torch.cuda.empty_cache()` when all pipelines terminate.
   - Fine-grained inference locks (`detector_inference_lock`, `reader_inference_lock`) protect concurrent tensor evaluations with bounded timeouts (`lock_timeout_s=0.2`).
2. **Pipeline State Isolation**:
   - Each pipeline maintains independent spatial tracking (`PlateIoUTracker`), temporal voting pools (`PlainCountVotingEngine`), and cooldown deduplication maps (`_cooldown_map`).
3. **Robust Quality Gating**:
   - Detections are filtered by minimum width (`min_plate_width_px`), sharpness (`min_sharpness` via Laplacian variance), and illumination bounds (`min_brightness`, `max_brightness`) before invoking OCR.
4. **Grammar-Validated Consensus**:
   - Only readings validated by Indonesian TNKB format rules (`GRAMMAR_VALID` status, or `REVIEW` if `allow_review: true`) with sufficient winner share (`min_winner_share`) emit `VEHICLE_LPR` events.

---

## 2. Modes of Operation

Configured via `mode` in `module_settings["vehicle_lpr"]`:

- **`"detector"` (Default)**:
  - Uses an external YOLO plate detection model to localize license plates anywhere in the full frame (or within `roi` if specified).
  - Recommended for moving traffic, multi-lane parking corridors, and variable vehicle positions.
- **`"roi"`**:
  - Direct static Region of Interest crop without running the plate detector model.
  - Recommended for fixed barrier gates, toll booths, and entry choke points where vehicle plates align consistently inside a pre-calibrated box.

---

## 3. Configuration Keys & Defaults

All options are configurable per-pipeline or globally under `module_settings["vehicle_lpr"]` in `configs/standalone.json`:

| Key | Type | Default | Description |
|---|---|---|---|
| `mode` | `string` | `"detector"` | Operational mode: `"detector"` or `"roi"`. |
| `detector_weights` | `string` | `runs/detect/.../best.pt` | Path to plate detector weights (overridable via `ANPR_DETECTOR_WEIGHTS`). |
| `detector_conf` | `float` | `0.25` | Confidence threshold for plate detection. |
| `detector_iou` | `float` | `0.45` | NMS IoU threshold for plate detection. |
| `detector_imgsz` | `int` | `640` | Input dimension for plate detector. |
| `reader_weights` | `string` | `runs/detect/.../last.pt` | Path to character reader weights (overridable via `ANPR_READER_WEIGHTS`). |
| `reader_conf` | `float` | `0.02` | Confidence threshold for character detector reader. |
| `reader_imgsz` | `int` | `320` | Input dimension for character reader. |
| `expected_sha256` | `string` | `"B82721AE..."` | SHA256 checksum verification for reader weights. |
| `device` | `int/str` | `0` | PyTorch device index (`0` for CUDA, or `"cpu"`). |
| `frame_stride` | `int` | `3` | Frame stride interval for detection runs. |
| `pad_ratio_x` | `float` | `0.08` | Proportional horizontal crop padding (8%). |
| `pad_ratio_y` | `float` | `0.15` | Proportional vertical crop padding (15%). |
| `min_plate_width_px`| `float` | `50.0` | Minimum plate bounding box width in pixels. |
| `min_sharpness` | `float` | `10.0` | Minimum Laplacian variance threshold. |
| `min_brightness` | `float` | `25.0` | Minimum grayscale mean brightness. |
| `max_brightness` | `float` | `240.0` | Maximum grayscale mean brightness (overexposure filter). |
| `min_observations` | `int` | `2` | Minimum voting observations before consensus check. |
| `min_winner_share` | `float` | `0.50` | Consensus threshold ratio among candidate readings. |
| `cooldown_s` | `float` | `10.0` | Deduplication window in seconds per plate string. |
| `lock_timeout_s` | `float` | `0.2` | Max wait time for inference lock before skip. |
| `allow_review` | `bool` | `false` | Whether to emit events for `REVIEW` status plates. |
| `save_snapshots` | `bool` | `false` | Whether to write crop snapshots to disk. |
| `snapshot_dir` | `string` | `null` | Target directory for plate crop snapshots. |

---

## 4. Skip Counters & Telemetry (`get_stats()`)

The plugin maintains exact bucket accounting for every strided detection:

- `detections_total`: Total plate bounding boxes detected across all strided frames.
- `skipped_too_small`: Plates with width < `min_plate_width_px`.
- `skipped_too_blurry`: Plate crops failing Laplacian variance (`< min_sharpness`).
- `skipped_too_dark`: Plate crops outside `[min_brightness, max_brightness]`.
- `skipped_lock_timeout`: Inference skipped because lock acquisition exceeded `lock_timeout_s` (0.2s).
- `skipped_after_consensus`: Detections on tracks that have already reached consensus and emitted.
- `skipped_cooldown`: Consensus reached but plate string was seen within `cooldown_s`.
- `reader_no_read`: Crops that yielded `NO_READ` or empty text.
- `reader_ok`: Observations successfully parsed and ingested into the voting engine.

**Reconciliation Invariant**:
```
detections_total == (
    skipped_too_small +
    skipped_too_blurry +
    skipped_too_dark +
    skipped_lock_timeout +
    skipped_after_consensus +
    skipped_cooldown +
    reader_no_read +
    reader_ok
)
```

Additional health counters:
- `stride_skipped_frames`: Intermediate frames skipped by `frame_stride`.
- `frames_without_detection`: Strided inference cycles where detector found zero plates.
- `events_emitted`: Total `VEHICLE_LPR` runtime events published.

---

## 5. Known Operational Limitations

> [!WARNING]
> **Camera Adequacy & Field-of-View Limitation**:
> Validation and integration tests conducted against `VideoProject2.mp4` represent reference integration clips and **do NOT demonstrate adequacy for deployed field cameras**.
> The deployed CCTV cameras have different mounting angles, optical zoom, lighting conditions, and lens distortions. Calibration of `min_plate_width_px`, `min_sharpness`, and detection confidence thresholds must be performed using actual camera footage from the physical installation site.

- **Night / Low-IR Conditions**: Infrared flare from reflective license plates or severe low-light noise may trigger `skipped_too_dark` or `skipped_too_blurry`. External white-light or IR illumination tuned for license plate capture is recommended.
- **Extreme Angled Views**: Recognition accuracy decreases significantly when plates exceed ~30 degrees yaw or pitch angle relative to the optical axis.
