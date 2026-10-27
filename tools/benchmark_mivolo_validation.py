"""
MiVOLO Standalone Model Validation & Performance Benchmarking Tool (Sprint H1.4.5).

Measures:
1. PyTorch model loading and initialization time.
2. CUDA vs CPU execution capability.
3. Warmup latency and single-image inference latency.
4. Scalability across batch sizes (1, 5, 10, 20 faces/persons).
5. TorchScript & ONNX export technical investigation.

NOTE: This is a standalone diagnostic script for Sprint H1.4.5 validation and does NOT touch or modify HumanRuntime.
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path
import numpy as np
import torch

# Add MiVOLO third-party directory to sys.path for standalone testing
MIVOLO_DIR = Path("camera_analytics/third_party/MiVOLO").resolve()
if str(MIVOLO_DIR) not in sys.path:
    sys.path.insert(0, str(MIVOLO_DIR))

from mivolo.model.create_timm_model import create_model

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("BenchmarkMiVOLO")


def benchmark_mivolo_standalone():
    print("\n========================================================")
    print("      MIVOLO STANDALONE MODEL VALIDATION & BENCHMARK    ")
    print("========================================================")

    device_str = "cuda" if torch.cuda.is_available() else "cpu"
    device = torch.device(device_str)
    print(f"[+] Execution Device: {device_str.upper()} ({torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'})")

    # 1. Measure Model Initialization Time
    t_start_init = time.perf_counter()
    weights_path = Path("camera_analytics/models/human/mivolo/weights/model.safetensors")
    
    # Create VOLO backbone (in_chans=6 for dual face+body stream, num_classes=3)
    model = create_model(
        "volo_d1_224",
        pretrained=False,
        num_classes=3,
        in_chans=6,
    )
    model.to(device)
    model.eval()
    init_time_ms = (time.perf_counter() - t_start_init) * 1000.0
    print(f"[+] Model Architecture Construction Time: {init_time_ms:.2f} ms")

    # 2. Warmup Execution
    dummy_input = torch.randn(1, 6, 224, 224, device=device)

    t_start_warmup = time.perf_counter()
    with torch.no_grad():
        _ = model(dummy_input)
        if torch.cuda.is_available():
            torch.cuda.synchronize()
    warmup_time_ms = (time.perf_counter() - t_start_warmup) * 1000.0
    print(f"[+] Hardware Warmup Time (1st Pass): {warmup_time_ms:.2f} ms")

    # 3. Scalability Benchmark across Batch Sizes (1, 5, 10, 20 faces/bodies)
    batch_sizes = [1, 5, 10, 20]
    results = {}

    for b in batch_sizes:
        b_input = torch.randn(b, 6, 224, 224, device=device)

        timings = []
        with torch.no_grad():
            for _ in range(30):
                t0 = time.perf_counter()
                _ = model(b_input)
                if torch.cuda.is_available():
                    torch.cuda.synchronize()
                elapsed = (time.perf_counter() - t0) * 1000.0
                timings.append(elapsed)

        avg_lat = float(np.mean(timings))
        p95_lat = float(np.percentile(timings, 95))
        fps = (1000.0 / avg_lat) * b
        results[b] = {"avg_ms": avg_lat, "p95_ms": p95_lat, "fps": fps}
        print(f"  [Batch {b:2d} faces/persons] Avg Latency: {avg_lat:6.2f} ms | P95: {p95_lat:6.2f} ms | Throughput: {fps:6.1f} crops/sec")

    # VRAM Memory Check
    vram_mb = torch.cuda.max_memory_allocated() / (1024 * 1024) if torch.cuda.is_available() else 0.0
    print(f"\n[+] Peak VRAM Memory Usage: {vram_mb:.2f} MB")

    # 4. TorchScript Investigation
    print("\n--- Investigating TorchScript Export Compatibility ---")
    try:
        traced_model = torch.jit.trace(model, dummy_input)
        print("[+] TorchScript (jit.trace) export: SUCCESSFUL!")
    except Exception as exc:
        print(f"[-] TorchScript (jit.trace) export failed: {exc}")

    # 5. ONNX Investigation
    print("\n--- Investigating ONNX Export Compatibility ---")
    try:
        import io
        buf = io.BytesIO()
        torch.onnx.export(
            model,
            dummy_input,
            buf,
            input_names=["input"],
            output_names=["output"],
            opset_version=14,
        )
        print("[+] ONNX export: SUCCESSFUL!")
    except Exception as exc:
        print(f"[-] ONNX export failed (Expected due to Volo transformer dynamic operators): {exc}")

    print("========================================================\n")


if __name__ == "__main__":
    benchmark_mivolo_standalone()
