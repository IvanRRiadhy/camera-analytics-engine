"""
Configuration schema, defaults, and environment resolution for Face Matching Plugin.
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _resolve_default_path(env_var: Optional[str], default_rel: str) -> str:
    """Resolve asset path from environment variable, frozen exe directory, or current working directory."""
    if env_var and os.environ.get(env_var):
        return os.environ[env_var]

    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        return str(exe_dir / default_rel)

    # In source mode, anchor to current working directory or relative path
    cwd_path = Path.cwd() / default_rel
    if cwd_path.exists():
        return str(cwd_path)

    # Fallback to repo root resolution
    repo_root = Path(__file__).resolve().parent.parent.parent
    repo_path = repo_root / default_rel
    if repo_path.exists():
        return str(repo_path)

    return str(cwd_path)


@dataclass
class FaceMatchConfig:
    """Operational configuration for Face Matching plugin.

    NOTE ON GATE THRESHOLDS:
    All gate values below (min_face_px, min_quality, cosine_threshold, min_margin,
    consensus_frames, consensus_window, track_cooldown_s) are PLACEHOLDERS for initial MVP
    bring-up and will be calibrated against empirical ROC/DET curves on real CCTV streams.
    """

    # Paths and Asset Bindings
    gallery_path: str = field(
        default_factory=lambda: _resolve_default_path("FACE_MATCH_GALLERY", os.path.join("data", "faces"))
    )
    yunet_weights: str = field(
        default_factory=lambda: _resolve_default_path(
            "FACE_DETECTOR_WEIGHTS", os.path.join("models", "face", "face_detection_yunet_2023mar.onnx")
        )
    )
    sface_weights: str = field(
        default_factory=lambda: _resolve_default_path(
            "FACE_RECOGNIZER_WEIGHTS", os.path.join("models", "face", "face_recognition_sface_2021dec.onnx")
        )
    )

    # Runtime Execution & Stride Policies
    frame_stride: int = 3
    detect_scale: float = 1.0
    score_threshold: float = 0.60  # YuNet face detection confidence threshold (PLACEHOLDER)
    lock_timeout_s: float = 0.05   # Shared inference lock acquisition timeout
    async_inference: bool = False  # Whether to run face inference on a dedicated background thread

    # Gate Thresholds (PLACEHOLDERS)
    min_face_px: int = 64          # Minimum face bounding box width in pixels
    min_quality: float = 0.30      # Minimum composite face quality score from FaceQualityEstimator
    cosine_threshold: float = 0.40 # Minimum cosine similarity to declare face candidate match
    min_margin: float = 0.05       # Minimum score delta between top-1 and top-2 candidate persons

    # Temporal Consensus & Emission Policies (PLACEHOLDERS)
    consensus_frames: int = 3      # Minimum matching observations required to confirm identity
    consensus_window: int = 15     # Sliding observation window size per track
    track_cooldown_s: float = 10.0 # Suppression window between repeated events for same person

    # Event & Telemetry Options
    emit_unknown: bool = False     # Whether to emit events for unassigned/unidentified tracks
    overlay_unknown: bool = True   # Whether live viewer displays bounding boxes for unknown tracks
    save_snapshots: bool = False   # Whether to write biometric face snapshots to disk
    max_tracks: int = 32           # Maximum concurrent active face tracks to maintain
    debug_scores: bool = True      # Whether to append score diagnostics to viewer box labels

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]] = None) -> FaceMatchConfig:
        """Construct FaceMatchConfig from dictionary (e.g. module_settings.face_matching)."""
        if not data:
            return cls()

        cfg = cls()

        # Handle string paths with env/frozen resolution
        if "gallery_path" in data and data["gallery_path"]:
            cfg.gallery_path = _resolve_default_path(None, str(data["gallery_path"]))
        if "yunet_weights" in data and data["yunet_weights"]:
            cfg.yunet_weights = _resolve_default_path(None, str(data["yunet_weights"]))
        if "sface_weights" in data and data["sface_weights"]:
            cfg.sface_weights = _resolve_default_path(None, str(data["sface_weights"]))

        if "frame_stride" in data:
            cfg.frame_stride = max(1, int(data["frame_stride"]))
        if "detect_scale" in data:
            cfg.detect_scale = float(data["detect_scale"])
        if "score_threshold" in data:
            cfg.score_threshold = float(data["score_threshold"])
        if "min_face_px" in data:
            cfg.min_face_px = int(data["min_face_px"])
        if "min_quality" in data:
            cfg.min_quality = float(data["min_quality"])
        if "cosine_threshold" in data:
            cfg.cosine_threshold = float(data["cosine_threshold"])
        if "min_margin" in data:
            cfg.min_margin = float(data["min_margin"])
        if "consensus_frames" in data:
            cfg.consensus_frames = int(data["consensus_frames"])
        if "consensus_window" in data:
            cfg.consensus_window = int(data["consensus_window"])
        if "track_cooldown_s" in data:
            cfg.track_cooldown_s = float(data["track_cooldown_s"])
        if "emit_unknown" in data:
            cfg.emit_unknown = bool(data["emit_unknown"])
        if "overlay_unknown" in data:
            cfg.overlay_unknown = bool(data["overlay_unknown"])
        if "save_snapshots" in data:
            cfg.save_snapshots = bool(data["save_snapshots"])
        if "max_tracks" in data:
            cfg.max_tracks = int(data["max_tracks"])
        if "debug_scores" in data:
            cfg.debug_scores = bool(data["debug_scores"])
        if "lock_timeout_s" in data:
            cfg.lock_timeout_s = float(data["lock_timeout_s"])
        if "async_inference" in data:
            cfg.async_inference = bool(data["async_inference"])

        return cfg

