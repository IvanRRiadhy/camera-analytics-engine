import logging
import threading
from typing import Dict, Any, Tuple, Optional
import torch

logger = logging.getLogger(__name__)


class SharedModelCache:
    """Thread-safe, reference-counted singleton cache for detector and reader models."""

    _instance_lock = threading.Lock()
    _detector_cache: Dict[Tuple[str, Any, int, float], Any] = {}
    _reader_cache: Dict[Tuple[str, Any, int, float], Any] = {}
    _ref_counts: Dict[str, int] = {"detector": 0, "reader": 0}

    # Fine-grained inference locks to allow timeout handling across pipelines
    detector_inference_lock = threading.Lock()
    reader_inference_lock = threading.Lock()

    @classmethod
    def get_detector(cls, weights: str, device: Any, imgsz: int, conf: float) -> Any:
        key = (str(weights), str(device), int(imgsz), float(conf))
        with cls._instance_lock:
            if key not in cls._detector_cache:
                from ultralytics import YOLO
                logger.info("[Plugin:Vehicle LPR] Loading Plate Detector YOLO model from '%s' on device %s...", weights, device)
                detector = YOLO(weights)
                cls._detector_cache[key] = detector
            else:
                logger.info("[Plugin:Vehicle LPR] Reusing shared plate detector for device %s.", device)
            cls._ref_counts["detector"] += 1
            return cls._detector_cache[key]

    @classmethod
    def get_reader(
        cls,
        weights: str,
        device: Any,
        imgsz: int,
        conf: float,
        expected_sha256: Optional[str] = None,
        config_path: Optional[str] = None,
    ) -> Any:
        key = (str(weights), str(device), int(imgsz), float(conf))
        with cls._instance_lock:
            if key not in cls._reader_cache:
                from anpr_v2.reader import CharDetectorReader
                logger.info("[Plugin:Vehicle LPR] Loading CharDetectorReader from '%s' on device %s...", weights, device)
                reader = CharDetectorReader(
                    weights_path=weights,
                    device=device,
                    imgsz=imgsz,
                    conf=conf,
                    expected_sha256=expected_sha256,
                    config_path=config_path,
                )
                cls._reader_cache[key] = reader
            else:
                logger.info("[Plugin:Vehicle LPR] Reusing shared CharDetectorReader for device %s.", device)
            cls._ref_counts["reader"] += 1
            return cls._reader_cache[key]

    @classmethod
    def release_detector(cls) -> None:
        with cls._instance_lock:
            cls._ref_counts["detector"] = max(0, cls._ref_counts["detector"] - 1)
            if cls._ref_counts["detector"] == 0:
                logger.info("[Plugin:Vehicle LPR] Releasing cached plate detector instances and clearing VRAM.")
                cls._detector_cache.clear()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()

    @classmethod
    def release_reader(cls) -> None:
        with cls._instance_lock:
            cls._ref_counts["reader"] = max(0, cls._ref_counts["reader"] - 1)
            if cls._ref_counts["reader"] == 0:
                logger.info("[Plugin:Vehicle LPR] Releasing cached CharDetectorReader instances and clearing VRAM.")
                cls._reader_cache.clear()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
