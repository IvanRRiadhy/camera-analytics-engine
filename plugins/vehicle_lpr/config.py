import os
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


def _resolve_default_path(env_var: str, default_rel: str) -> str:
    """Resolves model path from environment variable or relative to ANPR root."""
    if os.environ.get(env_var):
        return os.environ[env_var]
    import anpr_v2
    anpr_root = os.environ.get("ANPR_ROOT", str(Path(anpr_v2.__file__).resolve().parent.parent))
    return os.path.join(anpr_root, default_rel)


@dataclass
class VehicleLPRConfig:
    """Configuration schema and defaults for Vehicle LPR Plugin."""
    mode: str = "detector"                                       # "detector" or "roi"
    detector_weights: str = field(
        default_factory=lambda: _resolve_default_path(
            "ANPR_DETECTOR_WEIGHTS", os.path.join("runs", "detect", "indonesian_plate_yolo26_v1", "weights", "best.pt")
        )
    )
    detector_conf: float = 0.25
    detector_iou: float = 0.45
    detector_imgsz: int = 640
    reader_weights: str = field(
        default_factory=lambda: _resolve_default_path(
            "ANPR_READER_WEIGHTS", os.path.join("runs", "detect", "lprd_yolo26n_320", "weights", "last.pt")
        )
    )
    reader_config_path: Optional[str] = None
    reader_conf: float = 0.02
    reader_imgsz: int = 320
    expected_sha256: str = "B82721AE0D97595A9C5F17D614E63C6A44AE86BCD34389762EB39F6D1BF1960E"
    device: Any = 0
    frame_stride: int = 3
    pad_ratio_x: float = 0.08
    pad_ratio_y: float = 0.15
    min_plate_width_px: float = 50.0
    sharpness_ref_width: int = 160
    min_sharpness: float = 10.0
    min_brightness: float = 25.0
    max_brightness: float = 240.0
    min_observations: int = 3
    min_winner_share: float = 0.50
    emit_on_track_expiry: bool = True
    cooldown_s: float = 10.0
    allow_review: bool = False
    save_snapshots: bool = False
    snapshot_dir: Optional[str] = None
    roi: Optional[List[float]] = None                           # Normalized [x1, y1, x2, y2]
    detection_polygon: Optional[List[List[float]]] = None       # Normalized points [[x, y], ...]
    lock_timeout_s: float = 0.2                                 # Item 5: default 0.2s
    debug_crop_csv: Optional[str] = None                        # Optional debug CSV path (disabled by default)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VehicleLPRConfig":
        if not data:
            return cls()

        valid_fields = cls.__dataclass_fields__
        filtered: Dict[str, Any] = {}

        for k, v in data.items():
            if k not in valid_fields:
                logger.warning("[Plugin:Vehicle LPR] Unknown config key '%s' ignored.", k)
                continue

            # Validate types and ranges, falling back on default if invalid
            try:
                if k in ("detector_conf", "detector_iou", "reader_conf", "min_winner_share"):
                    fv = float(v)
                    if not (0.0 <= fv <= 1.0):
                        raise ValueError(f"{k} must be between 0.0 and 1.0")
                    filtered[k] = fv
                elif k in ("detector_imgsz", "reader_imgsz", "frame_stride", "min_observations", "sharpness_ref_width"):
                    iv = int(v)
                    if iv <= 0:
                        raise ValueError(f"{k} must be greater than 0")
                    filtered[k] = iv
                elif k in ("min_plate_width_px", "min_sharpness", "min_brightness", "max_brightness", "cooldown_s", "lock_timeout_s"):
                    fv = float(v)
                    if fv < 0:
                        raise ValueError(f"{k} cannot be negative")
                    filtered[k] = fv
                elif k in ("allow_review", "save_snapshots", "emit_on_track_expiry"):
                    filtered[k] = bool(v)
                elif k == "mode":
                    mode_str = str(v).lower().strip()
                    if mode_str not in ("detector", "roi"):
                        raise ValueError(f"Unknown mode '{v}'; must be 'detector' or 'roi'")
                    filtered[k] = mode_str
                else:
                    filtered[k] = v
            except (ValueError, TypeError) as val_err:
                logger.warning("[Plugin:Vehicle LPR] Invalid value for '%s' (%s): %s. Using default.", k, v, val_err)

        return cls(**filtered)
