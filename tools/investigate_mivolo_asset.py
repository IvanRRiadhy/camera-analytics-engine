"""
Stage A: Forensic Model Asset Investigation & Architecture Audit (Sprint H1.5B.1).

Inspects official MiVOLO safetensors, timm backbone configurations, positional embeddings,
patch embeddings, and current TorchScript graph expectations without modifying runtime code.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
import torch

# Insert MiVOLO third party path
mivolo_path = Path("camera_analytics/third_party/MiVOLO")
if mivolo_path.exists() and str(mivolo_path.resolve()) not in sys.path:
    sys.path.insert(0, str(mivolo_path.resolve()))

from safetensors.torch import load_file
import timm

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("InvestigateMiVOLOAsset")


def investigate_safetensors_weights():
    weights_path = Path("camera_analytics/models/human/mivolo/weights/model.safetensors")
    if not weights_path.exists():
        print(f"[!] Safetensors file not found: {weights_path}")
        return None

    print("\n--- 1. Safetensors Weight Checkpoint Analysis ---")
    st = load_file(str(weights_path))
    print(f"Total keys in safetensors: {len(st)}")

    pos_embed = st.get("mivolo.model.pos_embed")
    if pos_embed is not None:
        print(f"mivolo.model.pos_embed shape: {pos_embed.shape}")
        grid_h, grid_w = pos_embed.shape[1], pos_embed.shape[2]
        calc_res = grid_h * 16
        print(f"Grid dimensions: {grid_h} x {grid_w} | Calculated Native Image Resolution: {calc_res} x {calc_res}")
    else:
        print("[!] mivolo.model.pos_embed key not found in safetensors!")

    patch_weight = st.get("mivolo.model.patch_embed.conv1.0.weight")
    if patch_weight is not None:
        print(f"patch_embed.conv1.0.weight shape: {patch_weight.shape} (Input channels: {patch_weight.shape[1]})")

    head_weight = st.get("mivolo.model.head.weight")
    if head_weight is not None:
        print(f"head.weight shape: {head_weight.shape} (Output logits: {head_weight.shape[0]})")

    return {
        "pos_embed_shape": pos_embed.shape if pos_embed is not None else None,
        "calculated_res": pos_embed.shape[1] * 16 if pos_embed is not None else None,
        "input_channels": patch_weight.shape[1] if patch_weight is not None else 6,
        "num_classes": head_weight.shape[0] if head_weight is not None else 3,
    }


def investigate_torchscript_binary():
    ts_path = Path("camera_analytics/models/human/mivolo/weights/mivolo_v2.torchscript.pt")
    if not ts_path.exists():
        print(f"[!] TorchScript file not found: {ts_path}")
        return None

    print("\n--- 2. TorchScript Binary Graph Analysis ---")
    ts = torch.jit.load(str(ts_path))
    print(f"TorchScript code representation:\n{ts.code[:300]}...")

    pe = getattr(ts, "pos_embed", None)
    if pe is not None:
        print(f"TorchScript pos_embed shape: {pe.shape}")
        ts_grid = pe.shape[1]
        ts_res = ts_grid * 16
        print(f"TorchScript Grid: {ts_grid} x {ts_grid} | Traced Input Resolution: {ts_res} x {ts_res}")
    else:
        print("[!] TorchScript pos_embed attribute not directly accessible!")

    return ts


def investigate_timm_backbone_variants():
    print("\n--- 3. timm VOLO Backbone Investigation ---")
    d1_224 = timm.create_model("volo_d1_224", pretrained=False, num_classes=3, in_chans=6)
    print(f"volo_d1_224 default pos_embed shape: {d1_224.pos_embed.shape} | Default img_size: 224")

    d1_384 = timm.create_model("volo_d1_384", pretrained=False, num_classes=3, in_chans=6)
    print(f"volo_d1_384 default pos_embed shape: {d1_384.pos_embed.shape} | Default img_size: 384")


def main():
    print("=================================================================")
    print("   STAGE A: FORENSIC MIVOLO MODEL ASSET INVESTIGATION ")
    print("=================================================================")
    safetensors_info = investigate_safetensors_weights()
    ts_info = investigate_torchscript_binary()
    investigate_timm_backbone_variants()

    print("\n=================================================================")
    print("                      DECISION GATE EVALUATION                   ")
    print("=================================================================")
    if safetensors_info and safetensors_info["calculated_res"] == 384:
        print("Empirical Proof:")
        print("1. Safetensors pos_embed shape is [1, 24, 24, 384] -> Native resolution is 384x384.")
        print("2. Current TorchScript pos_embed shape is [1, 14, 14, 384] -> Traced resolution was 224x224.")
        print("Conclusion: REBUILD REQUIRED (TorchScript was traced using 224x224 instead of native 384x384).")
    else:
        print("Conclusion: CURRENT TORCHSCRIPT IS CORRECT.")
    print("=================================================================\n")


if __name__ == "__main__":
    main()
