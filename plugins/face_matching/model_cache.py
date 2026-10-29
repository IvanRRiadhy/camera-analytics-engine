"""
Shared Model and Gallery Cache with Thread-Safe Refcounting for Face Matching.
"""

from __future__ import annotations

import logging
import threading
from typing import Optional, Tuple

from camera_analytics.plugins.face_matching.config import FaceMatchConfig
from camera_analytics.plugins.face_matching.detector import YuNetDetector
from camera_analytics.plugins.face_matching.embedder import SFaceEmbedder
from camera_analytics.plugins.face_matching.gallery import FaceGallery

logger = logging.getLogger(__name__)


class SharedFaceModelCache:
    """Thread-safe reference-counted singleton cache for shared face models and gallery."""

    _instance: Optional[SharedFaceModelCache] = None
    _init_lock: threading.Lock = threading.Lock()

    # Dedicated hardware inference locks (ensures serial DNN execution per GPU/CPU thread)
    detector_inference_lock: threading.Lock = threading.Lock()
    embedder_inference_lock: threading.Lock = threading.Lock()

    def __init__(self) -> None:
        self._refcount: int = 0
        self._lock: threading.Lock = threading.Lock()
        self._detector: Optional[YuNetDetector] = None
        self._embedder: Optional[SFaceEmbedder] = None
        self._gallery: Optional[FaceGallery] = None

    @classmethod
    def get_instance(cls) -> SharedFaceModelCache:
        with cls._init_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def acquire(
        self,
        config: FaceMatchConfig,
    ) -> Tuple[YuNetDetector, SFaceEmbedder, FaceGallery]:
        """Acquire shared detector, embedder, and face gallery instances with refcounting."""
        with self._lock:
            if self._refcount == 0 or self._detector is None or self._embedder is None or self._gallery is None:
                logger.info("[SharedFaceModelCache] Loading shared detector, embedder, and gallery...")
                self._detector = YuNetDetector(
                    model_path=config.yunet_weights,
                    score_threshold=config.score_threshold,
                )
                self._embedder = SFaceEmbedder(
                    model_path=config.sface_weights,
                )
                self._gallery = FaceGallery.load(
                    gallery_path=config.gallery_path,
                    detector=self._detector,
                    embedder=self._embedder,
                    cosine_threshold=config.cosine_threshold,
                )
                logger.info("[SharedFaceModelCache] Models and gallery loaded successfully.")

            self._refcount += 1
            logger.info("[SharedFaceModelCache] Acquired models (Active refcount: %d)", self._refcount)
            return self._detector, self._embedder, self._gallery

    def release(self) -> None:
        """Release shared models; disposes instances when refcount reaches zero."""
        with self._lock:
            if self._refcount > 0:
                self._refcount -= 1
                logger.info("[SharedFaceModelCache] Released models (Remaining refcount: %d)", self._refcount)

            if self._refcount == 0:
                logger.info("[SharedFaceModelCache] Refcount is 0: Releasing detector, embedder, and gallery resources.")
                self._detector = None
                self._embedder = None
                self._gallery = None

