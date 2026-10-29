"""
Face Recognition Evaluation Harness & Measurement Script.

Inputs a dataset directory containing person subdirectories (e.g. data/faces_eval/<person>/*.jpg),
detects and embeds all facial images using YuNet and SFace, computes exhaustive genuine and impostor
cosine similarity scores, evaluates Genuine-Reject Rate (GRR) and Impostor-Accept Rate (IAR)
across threshold sweeps [0.20..0.60], and outputs detailed pair scores to CSV.

Usage::

    python camera_analytics/scripts/face_score_report.py --data-dir data/faces_eval --output-csv scores.csv
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path
from typing import List, NamedTuple, Optional, Tuple

import cv2
import numpy as np

# Ensure camera_analytics is importable
repo_root = Path(__file__).resolve().parent.parent
workspace_root = repo_root.parent
if str(workspace_root) not in sys.path:
    sys.path.insert(0, str(workspace_root))

from camera_analytics.plugins.face_matching.detector import YuNetDetector
from camera_analytics.plugins.face_matching.embedder import BaseFaceEmbedder, SFaceEmbedder


class ImageRecord(NamedTuple):
    """Metadata and feature representation for a processed identity image."""

    person_id: str
    image_path: Path
    embedding: np.ndarray
    detection_score: float


class PairScore(NamedTuple):
    """Pairwise comparison record between two face images."""

    pair_type: str  # "genuine" or "impostor"
    person_a: str
    image_a: str
    person_b: str
    image_b: str
    score: float


def load_and_embed_dataset(
    data_dir: Path,
    detector: YuNetDetector,
    embedder: SFaceEmbedder,
) -> Tuple[List[ImageRecord], int, int]:
    """Traverse data_dir/<person>/*.jpg, detect faces, and compute embeddings.

    Returns:
        Tuple of (records, total_images_scanned, detected_faces_count).
    """
    records: List[ImageRecord] = []
    total_scanned = 0
    detected_count = 0

    if not data_dir.is_dir():
        print(f"[!] Warning: Evaluation dataset directory not found: {data_dir}")
        return records, 0, 0

    valid_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

    # Sort persons for deterministic pair ordering
    person_dirs = sorted([d for d in data_dir.iterdir() if d.is_dir()])
    if not person_dirs:
        # Check if images are placed directly in data_dir
        direct_images = [f for f in data_dir.iterdir() if f.suffix.lower() in valid_extensions]
        if direct_images:
            print(f"[!] Warning: Images found directly in {data_dir}. Expected subdirectories per person: {data_dir}/<person>/*.jpg")

    for p_dir in person_dirs:
        person_id = p_dir.name
        img_files = sorted([f for f in p_dir.iterdir() if f.is_file() and f.suffix.lower() in valid_extensions])

        for img_path in img_files:
            total_scanned += 1
            frame = cv2.imread(str(img_path))
            if frame is None or frame.size == 0:
                print(f"[-] Could not read image: {img_path}")
                continue

            faces = detector.detect(frame)
            if not faces:
                print(f"[-] No face detected in: {img_path}")
                continue

            # Pick highest confidence face if multiple are present
            best_face = max(faces, key=lambda f: f.score)
            detected_count += 1

            embedding = embedder.embed(frame, best_face)
            records.append(
                ImageRecord(
                    person_id=person_id,
                    image_path=img_path,
                    embedding=embedding,
                    detection_score=best_face.score,
                )
            )

    return records, total_scanned, detected_count


def compute_all_pairs(records: List[ImageRecord]) -> Tuple[List[PairScore], List[float], List[float]]:
    """Generate all genuine and impostor pairs and compute cosine similarities."""
    pair_scores: List[PairScore] = []
    genuine_scores: List[float] = []
    impostor_scores: List[float] = []

    n = len(records)
    for i in range(n):
        for j in range(i + 1, n):
            rec_a = records[i]
            rec_b = records[j]

            sim = BaseFaceEmbedder.compute_similarity(rec_a.embedding, rec_b.embedding)
            pair_type = "genuine" if rec_a.person_id == rec_b.person_id else "impostor"

            pair_scores.append(
                PairScore(
                    pair_type=pair_type,
                    person_a=rec_a.person_id,
                    image_a=str(rec_a.image_path),
                    person_b=rec_b.person_id,
                    image_b=str(rec_b.image_path),
                    score=round(sim, 6),
                )
            )

            if pair_type == "genuine":
                genuine_scores.append(sim)
            else:
                impostor_scores.append(sim)

    return pair_scores, genuine_scores, impostor_scores


def print_score_distribution(name: str, scores: List[float]) -> None:
    """Print count, min, median, and max for a set of scores."""
    count = len(scores)
    if count == 0:
        print(f"  {name} Pairs: count=0, min=N/A, median=N/A, max=N/A")
        return

    arr = np.asarray(scores, dtype=np.float32)
    s_min = float(np.min(arr))
    s_med = float(np.median(arr))
    s_max = float(np.max(arr))
    print(f"  {name} Pairs ({count:,}): min={s_min:.4f}, median={s_med:.4f}, max={s_max:.4f}")


def compute_rates(
    genuine_scores: List[float],
    impostor_scores: List[float],
    thresholds: List[float],
) -> List[Tuple[float, float, float]]:
    """Compute Genuine-Reject Rate (GRR) and Impostor-Accept Rate (IAR) per threshold."""
    gen_arr = np.asarray(genuine_scores, dtype=np.float32) if genuine_scores else np.array([], dtype=np.float32)
    imp_arr = np.asarray(impostor_scores, dtype=np.float32) if impostor_scores else np.array([], dtype=np.float32)

    results: List[Tuple[float, float, float]] = []
    for th in thresholds:
        # Genuine-Reject Rate: fraction of genuine pairs where score < threshold
        grr = float(np.mean(gen_arr < th)) if gen_arr.size > 0 else 0.0
        # Impostor-Accept Rate: fraction of impostor pairs where score >= threshold
        iar = float(np.mean(imp_arr >= th)) if imp_arr.size > 0 else 0.0
        results.append((th, grr, iar))

    return results


def write_csv(pair_scores: List[PairScore], output_path: Path) -> None:
    """Write pairwise scores to CSV."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["pair_type", "person_a", "image_a", "person_b", "image_b", "score"])
        for p in pair_scores:
            writer.writerow([p.pair_type, p.person_a, p.image_a, p.person_b, p.image_b, p.score])


def main() -> int:
    parser = argparse.ArgumentParser(description="Face recognition evaluation harness and score distribution reporter.")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data/faces_eval"),
        help="Path to dataset root containing person subdirectories (default: data/faces_eval)",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("scores.csv"),
        help="Path to write pairwise scores CSV (default: scores.csv)",
    )
    parser.add_argument(
        "--yunet-weights",
        type=Path,
        default=repo_root / "models" / "face" / "face_detection_yunet_2023mar.onnx",
        help="Path to YuNet ONNX detector weights",
    )
    parser.add_argument(
        "--sface-weights",
        type=Path,
        default=repo_root / "models" / "face" / "face_recognition_sface_2021dec.onnx",
        help="Path to SFace ONNX recognizer weights",
    )
    args = parser.parse_args()

    print("=" * 70)
    print("  FACE RECOGNITION MEASUREMENT & EVALUATION HARNESS")
    print("=" * 70)
    print(f"Data directory : {args.data_dir.resolve()}")
    print(f"Output CSV     : {args.output_csv.resolve()}")
    print(f"YuNet weights  : {args.yunet_weights.resolve()}")
    print(f"SFace weights  : {args.sface_weights.resolve()}")
    print()

    # Verify model weights
    if not args.yunet_weights.is_file():
        print(f"[ERROR] YuNet weights file not found: {args.yunet_weights}")
        return 1
    if not args.sface_weights.is_file():
        print(f"[ERROR] SFace weights file not found: {args.sface_weights}")
        return 1

    # Initialize detector and embedder
    detector = YuNetDetector(args.yunet_weights)
    embedder = SFaceEmbedder(args.sface_weights)

    # Ingest and embed dataset
    records, total_scanned, detected_count = load_and_embed_dataset(args.data_dir, detector, embedder)

    print(f"[+] Total images scanned : {total_scanned}")
    print(f"[+] Faces detected       : {detected_count}")
    print(f"[+] Identities enrolled  : {len(set(r.person_id for r in records))}")
    print()

    if len(records) < 2:
        print("[!] Need at least 2 detected faces to evaluate pairwise similarity.")
        # Write empty CSV with header
        write_csv([], args.output_csv)
        print(f"[+] Empty CSV written to: {args.output_csv}")
        return 0

    # Compute pairwise similarities
    pair_scores, genuine_scores, impostor_scores = compute_all_pairs(records)

    print("=" * 70)
    print("  SCORE DISTRIBUTION SUMMARY")
    print("=" * 70)
    print_score_distribution("Genuine", genuine_scores)
    print_score_distribution("Impostor", impostor_scores)
    print()

    # Sweep thresholds 0.20..0.60 step 0.05
    thresholds = [round(t, 2) for t in np.arange(0.20, 0.601, 0.05).tolist()]
    rate_table = compute_rates(genuine_scores, impostor_scores, thresholds)

    print("=" * 70)
    print("  ERROR RATES ACROSS THRESHOLD SWEEP (GRR vs IAR)")
    print("=" * 70)
    print(f"  {'Threshold':<12} | {'Genuine-Reject (GRR)':<22} | {'Impostor-Accept (IAR)':<22}")
    print("  " + "-" * 62)
    for th, grr, iar in rate_table:
        print(f"  {th:<12.2f} | {grr * 100:<21.2f}% | {iar * 100:<21.2f}%")
    print("=" * 70)
    print("  [NOTE] Thresholds are reported neutrally. No operational threshold selected.")
    print("=" * 70)
    print()

    # Export to CSV
    write_csv(pair_scores, args.output_csv)
    print(f"[+] Successfully exported {len(pair_scores):,} pairwise scores to: {args.output_csv}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
