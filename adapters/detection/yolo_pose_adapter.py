"""
YOLO Pose adapter implementation.

Concrete implementation of DetectorPort for Ultralytics YOLO-Pose models (e.g. YOLO26m-Pose).
Isolates all dependencies on `ultralytics` and `torch` inside this adapter.
Converts Ultralytics inference outputs into framework-native DetectionResult and Detection objects.

Features:
    - Lazy loading of `ultralytics` and `torch` dependencies.
    - Automatic CUDA detection with graceful fallback to CPU.
    - 17 COCO keypoint mapping into PoseKeypoints.
    - Zero leaks of Ultralytics or Torch objects outside the adapter.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

import numpy as np

from camera_analytics.core.detection_set import DetectionSet
from camera_analytics.core.ports import DetectionResult, DetectorPort
from camera_analytics.models.detection import (
    BoundingBox,
    Detection,
    DetectionClass,
    Keypoint,
    PoseKeypoints,
)

if TYPE_CHECKING:
    from numpy.typing import NDArray

logger = logging.getLogger(__name__)


# COCO class index -> framework DetectionClass mapping
_COCO_CLASS_MAP: dict[int, DetectionClass] = {
    0: DetectionClass.PERSON,
}

# COCO keypoint names (17 keypoints in COCO format)
_COCO_KEYPOINT_NAMES: tuple[str, ...] = (
    "nose",
    "left_eye",
    "right_eye",
    "left_ear",
    "right_ear",
    "left_shoulder",
    "right_shoulder",
    "left_elbow",
    "right_elbow",
    "left_wrist",
    "right_wrist",
    "left_hip",
    "right_hip",
    "left_knee",
    "right_knee",
    "left_ankle",
    "right_ankle",
)


class YOLOPoseAdapter(DetectorPort):
    """Adapter for Ultralytics YOLO-Pose models (e.g. YOLO26m-Pose).

    Converts YOLO inference outputs into framework-native Detection
    and DetectionSet objects. Isolates all external AI libraries
    from the framework core.

    Args:
        confidence_threshold: Minimum confidence score for detections.
        iou_threshold: IoU threshold for non-maximum suppression (NMS).
    """

    def __init__(
        self,
        confidence_threshold: float = 0.5,
        iou_threshold: float = 0.45,
    ) -> None:
        self._confidence_threshold = confidence_threshold
        self._iou_threshold = iou_threshold
        self._model: Any = None
        self._device: str = "cpu"
        self._model_path: str = ""
        self._loaded: bool = False

    @property
    def name(self) -> str:
        """Detector name."""
        return "yolo_pose"

    @property
    def is_loaded(self) -> bool:
        """Whether the model is loaded and ready for inference."""
        return self._loaded

    @property
    def device(self) -> str:
        """Active compute device used by the model."""
        return self._device

    def load(self, model_path: str, device: str = "cuda") -> None:
        """Load the YOLO-Pose model.

        Performs lazy import of `ultralytics` and `torch`, validates model path,
        checks CUDA availability with automatic fallback to CPU, and initializes the model.

        Args:
            model_path: Path to model weights file (.pt) or official model name.
            device: Requested compute device ('cuda', 'cpu', 'mps').

        Raises:
            RuntimeError: If `ultralytics` package is not installed or model loading fails.
            FileNotFoundError: If a local model_path file does not exist.
        """
        # 1. Lazy import check for ultralytics and torch
        try:
            from ultralytics import YOLO
            import torch
        except ImportError as err:
            raise RuntimeError(
                "Ultralytics or PyTorch is not installed. "
                "Please install dependencies via 'pip install ultralytics torch'."
            ) from err

        # 2. Path validation if local file
        from camera_analytics.bootstrap.resource_manager import RuntimeResourceManager
        rm = RuntimeResourceManager.get_instance()
        resolved_model_path = str(rm.resolve_model_path(model_path))
        path_obj = Path(resolved_model_path)
        if model_path.endswith(".pt") and not path_obj.exists() and not model_path.startswith("yolo"):
            raise FileNotFoundError(f"YOLO model weights file not found: {model_path}")
        model_path = resolved_model_path

        # 3. Device management & CUDA fallback check
        target_device = device.lower()
        if target_device == "cuda":
            if not torch.cuda.is_available():
                logger.warning(
                    "CUDA requested for YOLOPoseAdapter, but CUDA is not available. "
                    "Falling back to CPU."
                )
                target_device = "cpu"
            else:
                logger.info("CUDA is available. YOLOPoseAdapter running on GPU: %s", torch.cuda.get_device_name(0))

        self._device = target_device
        self._model_path = model_path

        # 4. Model initialization
        try:
            logger.info("Loading YOLO-Pose model from '%s' on device '%s'...", model_path, self._device)
            self._model = YOLO(model_path)
            self._loaded = True
            logger.info("YOLOPoseAdapter successfully loaded on device '%s'", self._device)
        except Exception as exc:
            self._loaded = False
            self._model = None
            logger.exception("Failed to load YOLO model from '%s': %s", model_path, exc)
            raise RuntimeError(f"Failed to load YOLO model from '{model_path}': {exc}") from exc

    def detect(self, frame: NDArray[np.uint8]) -> DetectionResult:
        """Run YOLO-Pose detection on a frame image.

        Args:
            frame: Video frame image as HxWx3 uint8 numpy array (BGR).

        Returns:
            DetectionResult containing framework-native DetectionSet.

        Raises:
            RuntimeError: If detect() is called before load() or if inference fails.
        """
        if not self._loaded or self._model is None:
            raise RuntimeError("YOLOPoseAdapter must be loaded via load() before calling detect().")

        start = time.perf_counter()

        try:
            results = self._model(
                frame,
                conf=self._confidence_threshold,
                iou=self._iou_threshold,
                device=self._device,
                verbose=False,
            )
            detections = self._convert_results(results)
        except Exception as exc:
            logger.exception("YOLO inference failed: %s", exc)
            raise RuntimeError(f"YOLO inference failed: {exc}") from exc

        elapsed_ms = (time.perf_counter() - start) * 1000.0

        return DetectionResult(
            detections=DetectionSet(detections),
            model_name=self.name,
            inference_time_ms=elapsed_ms,
        )

    def release(self) -> None:
        """Release model resources and clear GPU cache if applicable."""
        self._model = None
        self._loaded = False

        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass

        logger.info("YOLOPoseAdapter resources released")

    # --- Result Conversion Logic ---

    def _convert_results(self, yolo_results: Any) -> list[Detection]:
        """Convert raw Ultralytics Results object to framework Detection instances.

        Args:
            yolo_results: Output list/object returned by Ultralytics YOLO inference.

        Returns:
            List of framework Detection objects (zero Ultralytics/Torch leaks).
        """
        detections: list[Detection] = []

        if yolo_results is None or len(yolo_results) == 0:
            return detections

        result = yolo_results[0]
        boxes = getattr(result, "boxes", None)

        if boxes is None or len(boxes) == 0:
            return detections

        # Helper to convert tensors or numpy arrays safely
        def _to_numpy(tensor_or_arr: Any) -> np.ndarray:
            if hasattr(tensor_or_arr, "cpu"):
                return tensor_or_arr.cpu().numpy()
            return np.asarray(tensor_or_arr)

        xyxy_arr = _to_numpy(boxes.xyxy)
        confs_arr = _to_numpy(boxes.conf)
        classes_arr = _to_numpy(boxes.cls).astype(int)

        # Keypoints extraction
        kps_xy_arr: Optional[np.ndarray] = None
        kps_conf_arr: Optional[np.ndarray] = None

        keypoints_obj = getattr(result, "keypoints", None)
        if keypoints_obj is not None and getattr(keypoints_obj, "xy", None) is not None:
            kps_xy_arr = _to_numpy(keypoints_obj.xy)
            if getattr(keypoints_obj, "conf", None) is not None:
                kps_conf_arr = _to_numpy(keypoints_obj.conf)

        for i in range(len(boxes)):
            cls_id = int(classes_arr[i])
            det_class = _COCO_CLASS_MAP.get(cls_id)

            # Skip classes not mapped in framework (only PERSON for pose)
            if det_class is None:
                continue

            bbox = BoundingBox(
                x1=int(xyxy_arr[i][0]),
                y1=int(xyxy_arr[i][1]),
                x2=int(xyxy_arr[i][2]),
                y2=int(xyxy_arr[i][3]),
            )

            confidence = float(confs_arr[i])

            pose_kps: Optional[PoseKeypoints] = None
            if kps_xy_arr is not None and i < len(kps_xy_arr):
                kp_conf_sub = kps_conf_arr[i] if kps_conf_arr is not None and i < len(kps_conf_arr) else None
                pose_kps = self._convert_keypoints(kps_xy_arr[i], kp_conf_sub)

            detections.append(
                Detection(
                    bbox=bbox,
                    confidence=confidence,
                    detection_class=det_class,
                    keypoints=pose_kps,
                )
            )

        return detections

    @staticmethod
    def _convert_keypoints(
        xy_arr: np.ndarray,
        conf_arr: Optional[np.ndarray] = None,
    ) -> PoseKeypoints:
        """Convert single person keypoints numpy arrays into framework PoseKeypoints.

        Args:
            xy_arr: Keypoint coordinates array of shape (17, 2).
            conf_arr: Keypoint confidence array of shape (17,) or None.

        Returns:
            PoseKeypoints containing 17 Keypoint objects.
        """
        keypoints_list: list[Keypoint] = []
        num_kps = min(len(xy_arr), len(_COCO_KEYPOINT_NAMES))

        for i in range(num_kps):
            x = float(xy_arr[i][0])
            y = float(xy_arr[i][1])
            kp_conf = float(conf_arr[i]) if conf_arr is not None and i < len(conf_arr) else 1.0

            keypoints_list.append(
                Keypoint(
                    x=x,
                    y=y,
                    confidence=kp_conf,
                )
            )

        return PoseKeypoints(keypoints=tuple(keypoints_list))
