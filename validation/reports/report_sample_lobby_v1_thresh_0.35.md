# Enterprise Analytics Validation Report — `sample_lobby_v1`
**Scenario**: PEAK_FOOT_TRAFFIC | **Tags**: `indoor, lobby, daylight, high_density`

## Overall Performance Summary
| Metric | Score / Value |
|---|---|
| **Precision** | `0.0909` |
| **Recall** | `0.6000` |
| **F1 Score** | `0.1579` |
| **Accuracy** | `0.0857` |
| **True Positives (TP)** | `3` |
| **False Positives (FP)** | `30` |
| **False Negatives (FN)** | `2` |
| **Avg Detection Delay** | `1018.33 ms` |

## System Resource & Throughput Metrics
| Resource Metric | Measured Value |
|---|---|
| **Throughput Speed** | `30.4 FPS` |
| **Avg Frame Latency** | `32.84 ms` |
| **CPU Utilization** | `104.8%` |
| **Memory Footprint** | `1205.7 MB` |
| **GPU Utilization** | `85.0%` |

## Event Type Accuracy Breakdown
| Event Type | TP | FP | FN | Precision | Recall | F1 Score |
|---|---|---|---|---|---|---|
| `ZONE_OCCUPANCY` | 1 | 7 | 0 | `0.1250` | `1.0000` | `0.2222` |
| `ZONE_ENTER` | 1 | 9 | 0 | `0.1000` | `1.0000` | `0.1818` |
| `DIRECTION_VIOLATION` | 1 | 3 | 0 | `0.2500` | `1.0000` | `0.4000` |
| `CROWD_ALERT` | 0 | 1 | 1 | `0.0000` | `0.0000` | `0.0000` |
| `QUEUE_ALERT` | 0 | 1 | 1 | `0.0000` | `0.0000` | `0.0000` |
| `INFO` | 0 | 6 | 0 | `0.0000` | `0.0000` | `0.0000` |
| `ZONE_EXIT` | 0 | 3 | 0 | `0.0000` | `0.0000` | `0.0000` |