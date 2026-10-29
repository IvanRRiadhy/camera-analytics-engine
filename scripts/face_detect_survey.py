"""
Face Detection Survey on CCTV Video Stream.

Performs face detection analysis across a real video clip at full resolution (1x)
and 2x upscale using YuNet. Evaluates face detection counts, face width distributions,
sharpness/quality using FaceQualityEstimator, exports detection CSV, saves top crops,
and saves annotated sample frames.

Usage::

    python camera_analytics/scripts/face_detect_survey.py --video data/clip.mp4 --out-dir data/face_survey
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

# Ensure workspace and camera_analytics packages are importable without shadowing stdlib logging
repo_root = Path(__file__).resolve().parent.parent
workspace_root = repo_root.parent
if str(workspace_root) not in sys.path:
    sys.path.insert(0, str(workspace_root))

from camera_analytics.core.human.quality_estimator import FaceQualityEstimator
from camera_analytics.plugins.face_matching.detector import FaceDetection, YuNetDetector


@dataclass(slots=True)
class SurveyDetection:
    """Record of a detected face instance during the video survey."""

    pass_name: str  # "1x_native" or "2x_upscale"
    frame_index: int
    timestamp_s: float
    box_x: float
    box_y: float
    box_w: float
    box_h: float
    score: float
    face_width_px: float
    face_quality: float
    landmarks: List[Tuple[float, float]]
    crop_bgr: Optional[np.ndarray] = None


def compute_width_buckets(widths: List[float]) -> Dict[str, int]:
    """Bucket face widths into threshold categories (>= 40, >= 64, >= 80, >= 112 px)."""
    return {
        "w_gte_40": sum(1 for w in widths if w >= 40.0),
        "w_gte_64": sum(1 for w in widths if w >= 64.0),
        "w_gte_80": sum(1 for w in widths if w >= 80.0),
        "w_gte_112": sum(1 for w in widths if w >= 112.0),
    }


def compute_score_buckets(scores: List[float]) -> Dict[str, int]:
    """Bucket face scores into threshold categories (>= 0.6, >= 0.8, >= 0.9)."""
    return {
        "score_gte_0_6": sum(1 for s in scores if s >= 0.6),
        "score_gte_0_8": sum(1 for s in scores if s >= 0.8),
        "score_gte_0_9": sum(1 for s in scores if s >= 0.9),
    }


def extract_face_crop(frame: np.ndarray, x: float, y: float, w: float, h: float) -> np.ndarray:
    """Safely extract cropped face region within image bounds."""
    img_h, img_w = frame.shape[:2]
    x1 = max(0, int(round(x)))
    y1 = max(0, int(round(y)))
    x2 = min(img_w, int(round(x + w)))
    y2 = min(img_h, int(round(y + h)))
    if x2 <= x1 or y2 <= y1:
        return np.zeros((0, 0, 3), dtype=np.uint8)
    return frame[y1:y2, x1:x2].copy()


def run_survey(
    video_path: Path,
    out_dir: Path,
    stride: int = 3,
    score_threshold: float = 0.6,
    yunet_weights: Optional[Path] = None,
) -> Tuple[List[SurveyDetection], List[SurveyDetection], Dict[str, Any]]:
    """Execute 1x native and 2x upscale face detection survey on video clip."""
    if yunet_weights is None:
        yunet_weights = repo_root / "models" / "face" / "face_detection_yunet_2023mar.onnx"

    if not yunet_weights.is_file():
        raise FileNotFoundError(f"YuNet weights not found at: {yunet_weights}")

    if not video_path.is_file():
        raise FileNotFoundError(f"Video file not found at: {video_path}")

    # Prepare output directories
    crops_dir = out_dir / "crops"
    annotated_dir = out_dir / "annotated"
    crops_dir.mkdir(parents=True, exist_ok=True)
    annotated_dir.mkdir(parents=True, exist_ok=True)

    # Initialize detectors
    detector_1x = YuNetDetector(yunet_weights, score_threshold=score_threshold)
    detector_2x = YuNetDetector(yunet_weights, score_threshold=score_threshold)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video stream: {video_path}")

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 25.0)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    print(f"Video Source   : {video_path.resolve()}")
    print(f"Resolution     : {width} x {height}")
    print(f"FPS            : {fps:.2f}")
    print(f"Total Frames   : {total_frames} (~{total_frames / max(1.0, fps):.2f}s)")
    print(f"Sampling Stride: every {stride} frame(s)")
    print(f"YuNet Threshold: {score_threshold}")
    print(f"Output Dir     : {out_dir.resolve()}")
    print()

    # Determine 6 evenly spaced frame indices for annotated snapshot exports
    if total_frames > 0:
        step_sample = max(1, total_frames // 6)
        annotated_target_indices = set(range(0, total_frames, step_sample)[:6])
    else:
        annotated_target_indices = {0, 60, 120, 180, 240, 300}

    detections_1x: List[SurveyDetection] = []
    detections_2x: List[SurveyDetection] = []

    frames_processed = 0
    frames_with_faces_1x = 0
    frames_with_faces_2x = 0

    frame_idx = 0
    annotated_saved_count = 0

    while True:
        ret, frame = cap.read()
        if not ret or frame is None:
            break

        if frame_idx % stride == 0:
            frames_processed += 1
            ts_sec = round(frame_idx / fps, 3)

            # --- Pass 1: Full-Resolution (1x native) ---
            faces_1x = detector_1x.detect(frame)
            frame_dets_1x: List[SurveyDetection] = []
            if faces_1x:
                frames_with_faces_1x += 1
                for f in faces_1x:
                    crop = extract_face_crop(frame, f.x, f.y, f.w, f.h)
                    quality = FaceQualityEstimator.evaluate_quality(face_crop=crop) if crop.size > 0 else 0.0
                    det = SurveyDetection(
                        pass_name="1x_native",
                        frame_index=frame_idx,
                        timestamp_s=ts_sec,
                        box_x=round(f.x, 2),
                        box_y=round(f.y, 2),
                        box_w=round(f.w, 2),
                        box_h=round(f.h, 2),
                        score=round(f.score, 4),
                        face_width_px=round(f.w, 2),
                        face_quality=quality,
                        landmarks=[(round(lx, 2), round(ly, 2)) for lx, ly in f.landmarks],
                        crop_bgr=crop,
                    )
                    frame_dets_1x.append(det)
                    detections_1x.append(det)

            # --- Pass 2: 2x Upscaled Frame ---
            frame_2x = cv2.resize(frame, (width * 2, height * 2), interpolation=cv2.INTER_LINEAR)
            faces_2x = detector_2x.detect(frame_2x)
            frame_dets_2x: List[SurveyDetection] = []
            if faces_2x:
                frames_with_faces_2x += 1
                for f in faces_2x:
                    # Remap coordinates from 2x space back to original 1x space
                    x_1x = f.x / 2.0
                    y_1x = f.y / 2.0
                    w_1x = f.w / 2.0
                    h_1x = f.h / 2.0
                    landmarks_1x = [(lx / 2.0, ly / 2.0) for lx, ly in f.landmarks]
                    crop = extract_face_crop(frame, x_1x, y_1x, w_1x, h_1x)
                    quality = FaceQualityEstimator.evaluate_quality(face_crop=crop) if crop.size > 0 else 0.0
                    det = SurveyDetection(
                        pass_name="2x_upscale",
                        frame_index=frame_idx,
                        timestamp_s=ts_sec,
                        box_x=round(x_1x, 2),
                        box_y=round(y_1x, 2),
                        box_w=round(w_1x, 2),
                        box_h=round(h_1x, 2),
                        score=round(f.score, 4),
                        face_width_px=round(w_1x, 2),
                        face_quality=quality,
                        landmarks=[(round(lx, 2), round(ly, 2)) for lx, ly in landmarks_1x],
                        crop_bgr=crop,
                    )
                    frame_dets_2x.append(det)
                    detections_2x.append(det)

            # Save annotated full frame at evenly spaced times
            if frame_idx in annotated_target_indices or (annotated_saved_count < 6 and frame_idx >= (annotated_saved_count * (total_frames // 6))):
                annotated_frame = frame.copy()
                # Draw 1x detections in Green
                for d in frame_dets_1x:
                    x1, y1 = int(round(d.box_x)), int(round(d.box_y))
                    x2, y2 = int(round(d.box_x + d.box_w)), int(round(d.box_y + d.box_h))
                    cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    label = f"1x w={d.face_width_px:.0f}px s={d.score:.2f} q={d.face_quality:.2f}"
                    cv2.putText(annotated_frame, label, (x1, max(15, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1, cv2.LINE_AA)

                # Draw 2x detections in Amber / Yellow (offset slightly if overlapping)
                for d in frame_dets_2x:
                    x1, y1 = int(round(d.box_x)), int(round(d.box_y))
                    x2, y2 = int(round(d.box_x + d.box_w)), int(round(d.box_y + d.box_h))
                    cv2.rectangle(annotated_frame, (x1 - 2, y1 - 2), (x2 + 2, y2 + 2), (0, 215, 255), 1)
                    label_2x = f"2x w={d.face_width_px:.0f}px s={d.score:.2f}"
                    cv2.putText(annotated_frame, label_2x, (x1, min(height - 6, y2 + 14)), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (0, 215, 255), 1, cv2.LINE_AA)

                header_text = f"Frame {frame_idx} ({ts_sec:.1f}s) | 1x Dets: {len(frame_dets_1x)} | 2x Dets: {len(frame_dets_2x)}"
                cv2.putText(annotated_frame, header_text, (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 255), 2, cv2.LINE_AA)

                annotated_path = annotated_dir / f"annotated_frame_{frame_idx:05d}_{ts_sec:.1f}s.jpg"
                cv2.imwrite(str(annotated_path), annotated_frame)
                annotated_saved_count += 1
                if frame_idx in annotated_target_indices:
                    annotated_target_indices.remove(frame_idx)

        frame_idx += 1

    cap.release()

    # --- Write Detections CSV ---
    csv_path = out_dir / "detections.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "pass",
            "frame_index",
            "timestamp_s",
            "box_x",
            "box_y",
            "box_w",
            "box_h",
            "score",
            "face_width_px",
            "face_quality",
            "landmarks",
        ])
        for det in detections_1x + detections_2x:
            writer.writerow([
                det.pass_name,
                det.frame_index,
                det.timestamp_s,
                det.box_x,
                det.box_y,
                det.box_w,
                det.box_h,
                det.score,
                det.face_width_px,
                det.face_quality,
                str(det.landmarks),
            ])

    # --- Save Top 40 Crops by Width ---
    # Prioritize 1x detections first, then 2x
    all_dets_with_crop = [d for d in detections_1x if d.crop_bgr is not None and d.crop_bgr.size > 0]
    if len(all_dets_with_crop) < 40:
        all_dets_with_crop.extend([d for d in detections_2x if d.crop_bgr is not None and d.crop_bgr.size > 0])

    top_crops = sorted(all_dets_with_crop, key=lambda d: d.face_width_px, reverse=True)[:40]
    for i, d in enumerate(top_crops, 1):
        crop_filename = f"crop_{i:02d}_f{d.frame_index:05d}_w{int(round(d.face_width_px))}px_s{d.score:.2f}_{d.pass_name}.jpg"
        crop_path = crops_dir / crop_filename
        if d.crop_bgr is not None:
            cv2.imwrite(str(crop_path), d.crop_bgr)

    meta = {
        "width": width,
        "height": height,
        "fps": fps,
        "total_frames": total_frames,
        "frames_processed": frames_processed,
        "frames_with_faces_1x": frames_with_faces_1x,
        "frames_with_faces_2x": frames_with_faces_2x,
        "csv_path": csv_path,
        "crops_dir": crops_dir,
        "annotated_dir": annotated_dir,
        "crops_saved": len(top_crops),
        "annotated_saved": annotated_saved_count,
    }

    return detections_1x, detections_2x, meta


def print_pass_summary(pass_label: str, detections: List[SurveyDetection], frames_processed: int, frames_with_faces: int) -> None:
    """Print structured summary metrics for a detection pass."""
    total_dets = len(detections)
    pct_frames = (frames_with_faces / max(1, frames_processed)) * 100.0

    print(f"=== PASS: {pass_label} ===")
    print(f"  Frames Processed         : {frames_processed}")
    print(f"  Frames with >=1 Face     : {frames_with_faces} ({pct_frames:.1f}%)")
    print(f"  Total Face Detections    : {total_dets}")

    if total_dets == 0:
        print("  Face Width min/med/max   : N/A")
        print("  Width Thresholds         : N/A")
        print("  Score Thresholds         : N/A")
        print()
        return

    widths = [d.face_width_px for d in detections]
    scores = [d.score for d in detections]
    w_min = float(np.min(widths))
    w_med = float(np.median(widths))
    w_max = float(np.max(widths))

    print(f"  Face Width (px)          : min={w_min:.1f}, median={w_med:.1f}, max={w_max:.1f}")

    w_buckets = compute_width_buckets(widths)
    print("  Width Distribution:")
    for th_key, th_val in [(">= 40 px", "w_gte_40"), (">= 64 px", "w_gte_64"), (">= 80 px", "w_gte_80"), (">= 112 px", "w_gte_112")]:
        cnt = w_buckets[th_val]
        pct = (cnt / total_dets) * 100.0
        print(f"    width {th_key:<10}: {cnt:4d} ({pct:5.1f}%)")

    s_buckets = compute_score_buckets(scores)
    print("  Detection Score Distribution:")
    for th_key, th_val in [(">= 0.60", "score_gte_0_6"), (">= 0.80", "score_gte_0_8"), (">= 0.90", "score_gte_0_9")]:
        cnt = s_buckets[th_val]
        pct = (cnt / total_dets) * 100.0
        print(f"    score {th_key:<10}: {cnt:4d} ({pct:5.1f}%)")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description="YuNet Face Detection Survey on Video Clip.")
    parser.add_argument("--video", type=Path, default=Path(r"E:\CCTV Analytics\data\Screen_Recording_20260622_113428_EZVIZ.mp4"), help="Video clip path")
    parser.add_argument("--out-dir", type=Path, default=Path("data/face_survey"), help="Output directory")
    parser.add_argument("--stride", type=int, default=3, help="Frame stride (default: 3)")
    parser.add_argument("--score-threshold", type=float, default=0.6, help="Confidence threshold (default: 0.6)")
    parser.add_argument("--yunet-weights", type=Path, default=repo_root / "models" / "face" / "face_detection_yunet_2023mar.onnx", help="YuNet weights path")
    args = parser.parse_args()

    print("=" * 75)
    print("  FACE DETECTION SURVEY ON CCTV VIDEO CLIP")
    print("=" * 75)

    dets_1x, dets_2x, meta = run_survey(
        video_path=args.video,
        out_dir=args.out_dir,
        stride=args.stride,
        score_threshold=args.score_threshold,
        yunet_weights=args.yunet_weights,
    )

    print("=" * 75)
    print("  SURVEY SUMMARY REPORT")
    print("=" * 75)
    print_pass_summary("1x Native Resolution", dets_1x, meta["frames_processed"], meta["frames_with_faces_1x"])
    print_pass_summary("2x Upscaled Resolution", dets_2x, meta["frames_processed"], meta["frames_with_faces_2x"])

    print("=" * 75)
    print("  ARTIFACT OUTPUT PATHS")
    print("=" * 75)
    print(f"  Detections CSV  : {meta['csv_path'].resolve()}")
    print(f"  Top Crops (40)  : {meta['crops_dir'].resolve()}")
    print(f"  Annotated Frames: {meta['annotated_dir'].resolve()}")
    print("=" * 75)

    return 0


if __name__ == "__main__":
    sys.exit(main())

