"""
Stage B: Native 384x384 TorchScript Rebuild & Validation Tool (Sprint H1.5B.1).

Rebuilds mivolo_v2.torchscript.pt using native 384x384 resolution (volo_d1_384 backbone),
verifies sample-by-sample functional equivalence against PyTorch Eager,
and measures multi-batch GPU performance benchmarks.
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path
import numpy as np
import torch

mivolo_path = Path("camera_analytics/third_party/MiVOLO")
if mivolo_path.exists() and str(mivolo_path.resolve()) not in sys.path:
    sys.path.insert(0, str(mivolo_path.resolve()))

from safetensors.torch import load_file
from mivolo.model.mi_volo import MiVOLO

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RebuildMiVOLO384")


def build_and_export_native_384_torchscript():
    weights_path = Path("camera_analytics/models/human/mivolo/weights/model.safetensors")
    output_path = Path("camera_analytics/models/human/mivolo/weights/mivolo_v2.torchscript.pt")
    device = torch.device("cpu")

    print("\n--- 1. Rebuilding Native 384x384 MiVOLO PyTorch Eager Model ---")
    st_weights = load_file(str(weights_path))

    # Strip prefix 'mivolo.model.' if present
    clean_state_dict = {}
    for k, v in st_weights.items():
        if k.startswith("mivolo.model."):
            clean_state_dict[k.replace("mivolo.model.", "")] = v
        else:
            clean_state_dict[k] = v

    from mivolo.model.create_timm_model import create_model
    model = create_model("mivolo_d1_384", pretrained=False, num_classes=3, in_chans=6)
    msg = model.load_state_dict(clean_state_dict, strict=False)
    print(f"Loaded safetensors into mivolo_d1_384: {msg}")
    model.eval()
    model.to(device)

    print("\n--- 2. Tracing Native 384x384 TorchScript Graph ---")
    dummy_input = torch.randn(1, 6, 384, 384, device=device)
    with torch.no_grad():
        _ = model(dummy_input)
        if device.type == "cuda":
            torch.cuda.synchronize()

    traced_model = torch.jit.trace(model, dummy_input)
    traced_model.save(str(output_path))
    print(f"[+] Native 384x384 TorchScript model exported to '{output_path}' ({output_path.stat().st_size / 1024 / 1024:.2f} MB)")

    return model, traced_model, device


def verify_sample_by_sample_equivalence(eager_model, ts_model, device, num_samples: int = 10):
    print(f"\n--- 3. Functional Equivalence Validation ({num_samples} samples) ---")
    
    age_errors = []
    gender_agreements = 0
    conf_diffs = []

    eager_model.eval()
    ts_model.eval()

    torch.manual_seed(42)
    np.random.seed(42)

    for i in range(num_samples):
        inp = torch.randn(1, 6, 384, 384, device=device)
        with torch.no_grad():
            out_eager = eager_model(inp).cpu().numpy()[0]
            out_ts = ts_model(inp).cpu().numpy()[0]

        # Age (idx 0)
        age_eager = float(out_eager[0])
        age_ts = float(out_ts[0])
        age_errors.append(abs(age_eager - age_ts))

        # Gender logits (idx 1, 2)
        g_eager_idx = int(np.argmax(out_eager[1:3]))
        g_ts_idx = int(np.argmax(out_ts[1:3]))
        if g_eager_idx == g_ts_idx:
            gender_agreements += 1

        exp_eager = np.exp(out_eager[1:3] - np.max(out_eager[1:3]))
        prob_eager = exp_eager / np.sum(exp_eager)

        exp_ts = np.exp(out_ts[1:3] - np.max(out_ts[1:3]))
        prob_ts = exp_ts / np.sum(exp_ts)

        conf_diffs.append(abs(prob_eager[g_eager_idx] - prob_ts[g_ts_idx]))

    mae = float(np.mean(age_errors))
    rmse = float(np.sqrt(np.mean(np.square(age_errors))))
    max_err = float(np.max(age_errors))
    agreement_pct = (gender_agreements / num_samples) * 100.0
    mean_conf_diff = float(np.mean(conf_diffs))

    print(f"  Age MAE          : {mae:.8f} years")
    print(f"  Age RMSE         : {rmse:.8f} years")
    print(f"  Age Max Error    : {max_err:.8f} years")
    print(f"  Gender Agreement : {agreement_pct:.2f}% ({gender_agreements}/{num_samples})")
    print(f"  Mean Conf Diff   : {mean_conf_diff:.8f}")

    assert mae < 0.1, f"Age MAE {mae} exceeds threshold 0.1"
    assert agreement_pct == 100.0, f"Gender agreement {agreement_pct}% is below 100%"
    assert mean_conf_diff < 0.001, f"Confidence diff {mean_conf_diff} exceeds threshold 0.001"

    print("[+] Sample-by-Sample Functional Equivalence Validation PASSED 100%!")
    return {
        "mae": mae,
        "rmse": rmse,
        "max_err": max_err,
        "agreement_pct": agreement_pct,
        "mean_conf_diff": mean_conf_diff,
    }


def benchmark_multi_batch_performance(ts_model, device):
    print("\n--- 4. Multi-Batch GPU Performance Benchmark (Native 384x384) ---")
    batch_sizes = [1, 2, 4, 8]
    results = {}

    ts_model.eval()

    for b in batch_sizes:
        dummy_batch = torch.randn(b, 6, 384, 384, device=device)
        
        # Warmup
        with torch.no_grad():
            for _ in range(1):
                _ = ts_model(dummy_batch)
                if device.type == "cuda":
                    torch.cuda.synchronize()

        # Measure 3 iterations
        t0 = time.perf_counter()
        with torch.no_grad():
            for _ in range(3):
                _ = ts_model(dummy_batch)
                if device.type == "cuda":
                    torch.cuda.synchronize()
        t1 = time.perf_counter()

        tot_time_s = t1 - t0
        avg_batch_lat_ms = (tot_time_s / 3.0) * 1000.0
        avg_crop_lat_ms = avg_batch_lat_ms / b
        throughput = (b * 3.0) / tot_time_s

        vram_mb = torch.cuda.max_memory_allocated(device) / 1024 / 1024 if device.type == "cuda" else 0.0

        print(f"  Batch {b:2d} | Batch Latency: {avg_batch_lat_ms:6.2f} ms | Crop Latency: {avg_crop_lat_ms:5.2f} ms | Throughput: {throughput:6.1f} crops/sec | VRAM: {vram_mb:.1f} MB")
        results[b] = {
            "batch_latency_ms": round(avg_batch_lat_ms, 2),
            "crop_latency_ms": round(avg_crop_lat_ms, 2),
            "throughput_crops_sec": round(throughput, 1),
            "vram_mb": round(vram_mb, 1),
        }

    return results


def main():
    print("=================================================================")
    print("   STAGE B: NATIVE 384 TORCHSCRIPT REBUILD & BENCHMARK ")
    print("=================================================================")
    eager_model, ts_model, device = build_and_export_native_384_torchscript()
    verify_sample_by_sample_equivalence(eager_model, ts_model, device, num_samples=100)
    benchmark_multi_batch_performance(ts_model, device)
    print("=================================================================\n")


if __name__ == "__main__":
    main()
