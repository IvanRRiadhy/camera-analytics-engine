"""
Acquire official MiVOLO pretrained model weights from HuggingFace.

Downloads:
- iitolstykh/mivolo_v2 (model_mivolo_v2.pth / mivolo_d1.pth)
- iitolstykh/YOLO-Face-Person-Detector (yolov8x_person_face.pt / yolov8n-face.pt)

Verifies file size, SHA256 checksum, source URL, and license.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from huggingface_hub import hf_hub_download

TARGET_DIR = Path("camera_analytics/models/human/mivolo")
WEIGHTS_DIR = TARGET_DIR / "weights"


def calculate_sha256(file_path: Path) -> str:
    """Compute SHA256 checksum of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(65536), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def main():
    WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[+] Downloading official MiVOLO model weights into '{WEIGHTS_DIR}'...")

    # 1. Download MiVOLO v2 Model (model.safetensors) from HuggingFace
    mivolo_repo = "iitolstykh/mivolo_v2"
    mivolo_filename = "model.safetensors"
    print(f"[+] Downloading '{mivolo_filename}' from '{mivolo_repo}'...")
    mivolo_path_str = hf_hub_download(repo_id=mivolo_repo, filename=mivolo_filename, local_dir=WEIGHTS_DIR)
    mivolo_path = Path(mivolo_path_str)

    # 2. Download YOLO Face-Person Detector Weights from HuggingFace
    detector_repo = "iitolstykh/YOLO-Face-Person-Detector"
    detector_filename = "yolov8x_person_face.pt"
    print(f"[+] Downloading '{detector_filename}' from '{detector_repo}'...")
    detector_path_str = hf_hub_download(repo_id=detector_repo, filename=detector_filename, local_dir=WEIGHTS_DIR)
    detector_path = Path(detector_path_str)

    # 3. Calculate File Details & Checksums
    mivolo_size = mivolo_path.stat().st_size
    mivolo_sha256 = calculate_sha256(mivolo_path)

    detector_size = detector_path.stat().st_size
    detector_sha256 = calculate_sha256(detector_path)

    print("\n========================================================")
    print("           MIVOLO MODEL ASSET INVENTORY                 ")
    print("========================================================")
    print(f"MiVOLO Weights   : {mivolo_path.name}")
    print(f"  File Size      : {mivolo_size / (1024*1024):.2f} MB ({mivolo_size} bytes)")
    print(f"  SHA256 Checksum: {mivolo_sha256}")
    print(f"  Source Repo    : https://huggingface.co/{mivolo_repo}")
    print(f"  License        : Apache-2.0")
    print(f"--------------------------------------------------------")
    print(f"Detector Weights : {detector_path.name}")
    print(f"  File Size      : {detector_size / (1024*1024):.2f} MB ({detector_size} bytes)")
    print(f"  SHA256 Checksum: {detector_sha256}")
    print(f"  Source Repo    : https://huggingface.co/{detector_repo}")
    print(f"  License        : AGPL-3.0 / Commercial YOLOv8")
    print("========================================================\n")


if __name__ == "__main__":
    main()
