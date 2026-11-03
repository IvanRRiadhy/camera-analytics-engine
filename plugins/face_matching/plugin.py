"""
Face Matching Analytics Vision Plugin.

Performs real-time face detection, metric embedding, local gallery matching,
temporal consensus identification, and viewer overlay exports.
"""

from __future__ import annotations

import collections
import logging
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from camera_analytics.core.human.quality_estimator import FaceQualityEstimator
from camera_analytics.events.models import BaseRuntimeEvent
from camera_analytics.plugins.face_matching.config import FaceMatchConfig
from camera_analytics.plugins.face_matching.consensus import (
    ConsensusBuffer,
    FaceObservation,
    PersonCooldownManager,
)
from camera_analytics.plugins.face_matching.detector import FaceDetection, YuNetDetector
from camera_analytics.plugins.face_matching.embedder import SFaceEmbedder
from camera_analytics.plugins.face_matching.gallery import FaceGallery, PersonCandidate
from camera_analytics.plugins.face_matching.model_cache import SharedFaceModelCache
from camera_analytics.plugins.face_matching.tracker import FaceIoUTracker, FaceTrack
from camera_analytics.plugins.framework.context import PluginContext
from camera_analytics.plugins.framework.states import PluginState
from camera_analytics.sdk.base_plugin import BaseAnalyticsPlugin

logger = logging.getLogger(__name__)


class FaceMatchingPlugin(BaseAnalyticsPlugin):
    """Production Face Matching & Identity Identification Plugin."""

    def __init__(self, name: str = "Face Matching", version: str = "1.0.0", description: str = "", config: Optional[FaceMatchConfig] = None) -> None:
        super().__init__(name=name, version=version, description=description)
        self.config: FaceMatchConfig = config or FaceMatchConfig()

        # Shared component references (acquired via SharedFaceModelCache)
        self.detector: Optional[YuNetDetector] = None
        self.embedder: Optional[SFaceEmbedder] = None
        self.gallery: Optional[FaceGallery] = None

        # Tracking & Temporal Consensus
        self.tracker: FaceIoUTracker = FaceIoUTracker(max_lost_strides=10)
        self._consensus_buffers: Dict[int, ConsensusBuffer] = {}
        self._cooldown_manager: PersonCooldownManager = PersonCooldownManager()

        # Latency metric collections
        self._detect_latencies_ms: List[float] = []
        self._embed_latencies_ms: List[float] = []

        # Operational Statistics
        self.stats: Dict[str, Any] = {
            "faces_detected": 0,
            "skipped_too_small": 0,
            "skipped_low_quality": 0,
            "matched_below_threshold": 0,
            "rejected_low_margin": 0,
            "events_emitted": 0,
            "unknown_tracks": 0,
            "frames_processed": 0,
            "stride_skipped_frames": 0,
            "async_frames_replaced": 0,
            "async_worker_errors": 0,
        }

        # Async inference infrastructure
        self._worker_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._input_event = threading.Event()
        self._input_lock = threading.Lock()
        self._pending_frame_data: Optional[Tuple[np.ndarray, int, float, int, int]] = None
        self._output_lock = threading.Lock()
        self._completed_events: collections.deque[BaseRuntimeEvent] = collections.deque(maxlen=100)
        self._latest_face_overlays: List[Dict[str, Any]] = []
        self._worker_busy_accum: float = 0.0
        self._stats_lock = threading.Lock()

        # Camera suitability diagnostic tracking
        self._unsuitable_warned: bool = False
        self._face_detected_start_time: Optional[float] = None
        self._detected_widths_window: List[float] = []

        # Periodic status logging
        self._last_stats_log_time: float = 0.0

    def initialize(self, context: PluginContext) -> bool:
        """Initialize plugin, load configuration, and acquire shared face models."""
        self.context = context
        logger.info("[Plugin:Face Matching] Initializing for pipeline '%s'...", context.pipeline_id)

        try:
            # Extract configuration from module_settings.face_matching or direct dict
            mod_settings = context.config if isinstance(context.config, dict) else {}
            if "face_matching" in mod_settings and isinstance(mod_settings["face_matching"], dict):
                raw_cfg = mod_settings["face_matching"]
            else:
                raw_cfg = mod_settings

            self.config = FaceMatchConfig.from_dict(raw_cfg)

            # Acquire models through SharedFaceModelCache
            cache = SharedFaceModelCache.get_instance()
            self.detector, self.embedder, self.gallery = cache.acquire(self.config)

            # Configure tracker & consensus managers
            self.tracker = FaceIoUTracker(max_lost_strides=self.config.consensus_window)
            self._cooldown_manager = PersonCooldownManager(cooldown_s=self.config.track_cooldown_s)

            self.state = PluginState.INITIALIZED
            logger.info("[Plugin:Face Matching] Successfully initialized pipeline '%s'.", context.pipeline_id)
            return True

        except Exception as exc:
            self.state = PluginState.FAILED
            logger.error("[Plugin:Face Matching] Initialization FAILED in pipeline '%s': %s", context.pipeline_id, exc, exc_info=True)
            return False

    def start(self) -> None:
        """Start active execution state and launch async inference worker if enabled."""
        super().start()
        if self.config.async_inference:
            self._start_worker_thread()

    def _start_worker_thread(self) -> None:
        """Start background worker thread for asynchronous face inference."""
        with self._input_lock:
            if self._worker_thread is None or not self._worker_thread.is_alive():
                self._stop_event.clear()
                pipeline_id = getattr(self.context, "pipeline_id", "default") if self.context else "default"
                self._worker_thread = threading.Thread(
                    target=self._async_worker_loop,
                    name=f"FaceMatchingWorker-{pipeline_id}",
                    daemon=True,
                )
                self._worker_thread.start()
                logger.info("[Plugin:Face Matching] Async inference worker thread started for pipeline '%s'.", pipeline_id)

    def _async_worker_loop(self) -> None:
        """Continuous background inference loop processing latest frame."""
        logger.debug("[Plugin:Face Matching] Async inference worker loop running.")
        while not self._stop_event.is_set():
            flag = self._input_event.wait(timeout=0.1)
            if self._stop_event.is_set():
                break
            if not flag:
                continue

            with self._input_lock:
                data = self._pending_frame_data
                self._pending_frame_data = None
                self._input_event.clear()

            if data is None:
                continue

            frame, frame_idx, now_ts, h, w = data
            t0 = time.perf_counter()
            try:
                new_events, overlays = self._run_inference_pipeline(frame, frame_idx, now_ts, h, w)
                with self._output_lock:
                    for ev in new_events:
                        self._completed_events.append(ev)
                    self._latest_face_overlays = overlays
            except Exception as exc:
                self.stats["async_worker_errors"] += 1
                logger.error(
                    "[Plugin:Face Matching] Async worker error on frame %d: %s",
                    frame_idx,
                    exc,
                    exc_info=True,
                )
            finally:
                dur = time.perf_counter() - t0
                with self._stats_lock:
                    self._worker_busy_accum += dur

        logger.debug("[Plugin:Face Matching] Async inference worker loop exited.")

    def _run_inference_pipeline(
        self, frame: np.ndarray, frame_idx: int, now_ts: float, h: int, w: int
    ) -> Tuple[List[BaseRuntimeEvent], List[Dict[str, Any]]]:
        """Core inference logic: detection, tracking, embedding, consensus, and overlay generation."""
        events: List[BaseRuntimeEvent] = []

        # 1. Face Detection Pass (YuNet)
        detections: List[FaceDetection] = []
        if self.detector is not None:
            acquired_det = SharedFaceModelCache.detector_inference_lock.acquire(timeout=self.config.lock_timeout_s)
            if acquired_det:
                try:
                    t0_det = time.perf_counter()
                    if self.config.detect_scale != 1.0:
                        d_w = int(w * self.config.detect_scale)
                        d_h = int(h * self.config.detect_scale)
                        frame_scaled = cv2.resize(frame, (d_w, d_h), interpolation=cv2.INTER_LINEAR)
                        raw_dets = self.detector.detect(frame_scaled)
                        scale_inv = 1.0 / self.config.detect_scale
                        for rd in raw_dets:
                            box_scaled = (rd.x * scale_inv, rd.y * scale_inv, rd.w * scale_inv, rd.h * scale_inv)
                            landmarks_scaled = [(lx * scale_inv, ly * scale_inv) for lx, ly in rd.landmarks]
                            detections.append(FaceDetection(
                                box=box_scaled,
                                landmarks=landmarks_scaled,
                                score=rd.score,
                                raw_face=rd.raw_face * scale_inv if hasattr(rd, "raw_face") else np.array([]),
                            ))
                    else:
                        detections = self.detector.detect(frame)

                    det_ms = (time.perf_counter() - t0_det) * 1000.0
                    self._detect_latencies_ms.append(det_ms)
                finally:
                    SharedFaceModelCache.detector_inference_lock.release()
            else:
                logger.debug("[Plugin:Face Matching] Detector inference lock timeout (frame %d)", frame_idx)

        self.stats["faces_detected"] += len(detections)

        # Camera suitability diagnostic: check if faces are continuously below min_face_px
        if detections:
            for d in detections:
                self._detected_widths_window.append(d.w)
                if len(self._detected_widths_window) > 200:
                    self._detected_widths_window.pop(0)

            any_passed_width = any(d.w >= self.config.min_face_px for d in detections)
            if any_passed_width:
                self._face_detected_start_time = None
            else:
                if self._face_detected_start_time is None:
                    self._face_detected_start_time = now_ts
                elif (now_ts - self._face_detected_start_time) >= 30.0 and not self._unsuitable_warned:
                    median_w = float(np.median(self._detected_widths_window)) if self._detected_widths_window else 0.0
                    logger.warning(
                        "[Plugin:Face Matching] Camera may be unsuitable for face recognition: "
                        "detected faces have consistently been below min_face_px=%d for %.1fs (median detected width: %.1fpx)",
                        self.config.min_face_px, now_ts - self._face_detected_start_time, median_w
                    )
                    self._unsuitable_warned = True

        # 2. Spatial IoU Tracking Association
        active_tracks, expired_tracks = self.tracker.update(detections, frame_idx)

        # Clean up expired track consensus buffers (prevent memory leaks)
        for exp_tr in expired_tracks:
            self._consensus_buffers.pop(exp_tr.track_id, None)

        # 3. Process Each Detection Associated with Active Tracks
        for track in active_tracks:
            if track.time_since_update != 0:
                continue  # Not detected on current frame

            tw = track.w
            th = track.h

            # Width gate
            if tw < self.config.min_face_px:
                self.stats["skipped_too_small"] += 1
                track.state = "unknown"
                continue

            # Safe bounded crop extraction
            x1 = max(0, int(round(track.x1)))
            y1 = max(0, int(round(track.y1)))
            x2 = min(w, int(round(track.x2)))
            y2 = min(h, int(round(track.y2)))
            crop = frame[y1:y2, x1:x2].copy()

            if crop.size == 0:
                continue

            # Quality gate
            quality_score = FaceQualityEstimator.evaluate_quality(face_crop=crop)
            if quality_score < self.config.min_quality:
                self.stats["skipped_low_quality"] += 1
                track.state = "unknown"
                continue

            # Metric Alignment & Feature Embedding
            candidate_person_id: Optional[str] = None
            top1_score = 0.0
            margin = 0.0
            top1_meta: Dict[str, Any] = {}
            top1_name = "Unknown"

            if self.embedder is not None and self.gallery is not None:
                acquired_emb = SharedFaceModelCache.embedder_inference_lock.acquire(timeout=self.config.lock_timeout_s)
                if acquired_emb:
                    try:
                        t0_emb = time.perf_counter()
                        raw_box = np.array([track.x1, track.y1, tw, th], dtype=np.float32)
                        lk_flat = [coord for pt in track.landmarks for coord in pt] if len(track.landmarks) == 5 else [0.0] * 10
                        raw_arr = np.array(list(raw_box) + lk_flat + [track.conf], dtype=np.float32)
                        det_obj = FaceDetection(
                            box=(track.x1, track.y1, tw, th),
                            landmarks=track.landmarks,
                            score=track.conf,
                            raw_face=raw_arr,
                        )

                        embedding = self.embedder.embed(frame, det_obj)
                        emb_ms = (time.perf_counter() - t0_emb) * 1000.0
                        self._embed_latencies_ms.append(emb_ms)

                        # Gallery Match (top 2 distinct persons)
                        candidates = self.gallery.match(embedding, top_k=2)
                        if candidates:
                            top1 = candidates[0]
                            top1_score = top1.score
                            top1_name = top1.full_name
                            top1_meta = dict(top1.metadata)

                            if len(candidates) > 1:
                                margin = round(top1.score - candidates[1].score, 4)
                            else:
                                margin = round(top1.score, 4)

                            # Gate: Cosine threshold & minimum margin
                            if top1_score < self.config.cosine_threshold:
                                self.stats["matched_below_threshold"] += 1
                                candidate_person_id = None
                            elif margin < self.config.min_margin:
                                self.stats["rejected_low_margin"] += 1
                                candidate_person_id = None
                            else:
                                candidate_person_id = top1.person_id

                    finally:
                        SharedFaceModelCache.embedder_inference_lock.release()

            # Record Observation in Track Consensus Buffer
            buf = self._consensus_buffers.setdefault(
                track.track_id, ConsensusBuffer(window_size=self.config.consensus_window)
            )
            buf.add_observation(
                FaceObservation(
                    person_id=candidate_person_id,
                    score=top1_score,
                    margin=margin,
                    timestamp_s=now_ts,
                    frame_idx=frame_idx,
                    metadata=top1_meta,
                )
            )

            # Temporal Consensus Evaluation
            c_res = buf.evaluate_consensus(
                cosine_threshold=self.config.cosine_threshold,
                min_margin=self.config.min_margin,
                consensus_frames=self.config.consensus_frames,
            )

            if c_res is not None:
                track.state = "identified"
                track.identified_person_id = c_res.person_id
                track.identified_full_name = top1_name
                track.identified_score = c_res.best_score
                track.identified_margin = c_res.best_margin
                track.identified_meta = c_res.metadata

                # Event emission: strictly once per track, with per-person cooldown
                if not track.has_emitted:
                    if self._cooldown_manager.is_cooled_down(c_res.person_id, now_ts):
                        norm_bbox = [
                            round(track.x1 / max(1, w), 4),
                            round(track.y1 / max(1, h), 4),
                            round(track.x2 / max(1, w), 4),
                            round(track.y2 / max(1, h), 4),
                        ]

                        clean_meta = dict(c_res.metadata)
                        clean_meta.pop("person_id", None)
                        clean_meta.pop("full_name", None)

                        event = BaseRuntimeEvent(
                            pipeline_assignment_id=getattr(self.context, "pipeline_id", "default") if self.context else "default",
                            camera_id=getattr(self.context, "camera_id", "c1") if self.context else "c1",
                            plugin_name=self.name,
                            event_type="FACE_IDENTIFIED",
                            confidence=c_res.best_score,
                            track_id=track.track_id,
                            bounding_box=norm_bbox,
                            snapshot_path=None,
                            attributes={
                                "person_id": c_res.person_id,
                                "full_name": top1_name,
                                "similarity": c_res.best_score,
                                "margin": c_res.best_margin,
                                "matched_frames": c_res.matched_frames,
                                "face_width_px": round(tw, 1),
                                "face_quality": round(quality_score, 3),
                                "face_box": [int(track.x1), int(track.y1), int(tw), int(th)],
                                "frame_number": frame_idx,
                                "metadata": clean_meta,
                            },
                        )
                        setattr(event, "frame_number", frame_idx)
                        if hasattr(event, "metadata") and isinstance(event.metadata, dict):
                            event.metadata["frame_number"] = frame_idx
                        events.append(event)
                        self.emit(event)
                        track.has_emitted = True
                        self.stats["events_emitted"] += 1
                        self._cooldown_manager.record_emission(c_res.person_id, now_ts)
                        logger.info(
                            "[Plugin:Face Matching] IDENTIFIED person '%s' on track %d (similarity: %.4f, margin: %.4f)",
                            c_res.person_id, track.track_id, c_res.best_score, c_res.best_margin
                        )
            else:
                if track.state != "identified":
                    track.state = "unknown" if candidate_person_id is None else "tracking"
                    if track.state == "unknown":
                        self.stats["unknown_tracks"] += 1

        overlays = self._build_overlays()
        return events, overlays

    def _build_overlays(self) -> List[Dict[str, Any]]:
        """Generate overlay dictionary list from current tracker tracks."""
        active_face_overlays: List[Dict[str, Any]] = []
        for tid, f_track in self.tracker.tracks.items():
            if f_track.state == "identified":
                label = f"{f_track.identified_full_name or f_track.identified_person_id} ({f_track.identified_person_id}) {f_track.identified_score:.2f}"
            else:
                if self.config.debug_scores and f_track.identified_score > 0.0:
                    label = f"? {f_track.identified_score:.2f}"
                else:
                    label = "?"

            active_face_overlays.append({
                "track_id": tid,
                "bbox": [float(f_track.x1), float(f_track.y1), float(f_track.x2), float(f_track.y2)],
                "label": label,
                "person_id": f_track.identified_person_id or "",
                "similarity": f_track.identified_score,
                "state": f_track.state,
            })
        return active_face_overlays

    def process(self, context: Any) -> List[BaseRuntimeEvent]:
        """Execute face detection, tracking, metric embedding, consensus, and event emission."""
        if self.state != PluginState.RUNNING:
            return []

        frame = getattr(context, "frame", None)
        if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0 or frame.ndim < 2:
            return []

        frame_idx = int(getattr(context, "frame_index", 0))
        now_ts = float(getattr(context, "timestamp_utc", time.time()))
        h, w = frame.shape[:2]

        events: List[BaseRuntimeEvent] = []

        try:
            if not self.config.async_inference:
                # Synchronous execution path
                is_detector_turn = (frame_idx % max(1, self.config.frame_stride)) == 0
                if not is_detector_turn:
                    self.stats["stride_skipped_frames"] += 1
                    active_face_overlays = self._build_overlays()
                else:
                    self.stats["frames_processed"] += 1
                    events, active_face_overlays = self._run_inference_pipeline(frame, frame_idx, now_ts, h, w)

                if hasattr(context, "metadata") and isinstance(context.metadata, dict):
                    context.metadata["face_matches"] = active_face_overlays
                setattr(context, "face_matches", active_face_overlays)

            else:
                # Asynchronous execution path
                if (self._worker_thread is None or not self._worker_thread.is_alive()) and not self._stop_event.is_set():
                    self._start_worker_thread()

                is_detector_turn = (frame_idx % max(1, self.config.frame_stride)) == 0
                if not is_detector_turn:
                    self.stats["stride_skipped_frames"] += 1
                else:
                    self.stats["frames_processed"] += 1
                    frame_copy = frame.copy()
                    with self._input_lock:
                        if self._pending_frame_data is not None:
                            self.stats["async_frames_replaced"] += 1
                        self._pending_frame_data = (frame_copy, frame_idx, now_ts, h, w)
                        self._input_event.set()

                # Drain completed events and latest overlays
                with self._output_lock:
                    events = list(self._completed_events)
                    self._completed_events.clear()
                    active_face_overlays = list(self._latest_face_overlays)

                if hasattr(context, "metadata") and isinstance(context.metadata, dict):
                    context.metadata["face_matches"] = active_face_overlays
                setattr(context, "face_matches", active_face_overlays)

            # Periodic (10s) Operational Health Status Log
            if now_ts - self._last_stats_log_time >= 10.0:
                elapsed = max(0.001, now_ts - self._last_stats_log_time)
                self._last_stats_log_time = now_ts
                with self._stats_lock:
                    busy_accum = self._worker_busy_accum
                    self._worker_busy_accum = 0.0

                if self.config.async_inference:
                    worker_busy_pct = max(0.0, min(100.0, (busy_accum / elapsed) * 100.0))
                else:
                    worker_busy_pct = 0.0

                det_lat_str = self._format_latencies(self._detect_latencies_ms)
                emb_lat_str = self._format_latencies(self._embed_latencies_ms)
                logger.info(
                    "[Plugin:Face Matching Stats] Detections=%d | Emitted=%d | Small=%d | LowQ=%d | BelowTh=%d | LowMargin=%d | Unknown=%d | DetectLatency=[%s] | EmbedLatency=[%s] | AsyncReplaced=%d | WorkerBusy=%.1f%%",
                    self.stats["faces_detected"],
                    self.stats["events_emitted"],
                    self.stats["skipped_too_small"],
                    self.stats["skipped_low_quality"],
                    self.stats["matched_below_threshold"],
                    self.stats["rejected_low_margin"],
                    self.stats["unknown_tracks"],
                    det_lat_str,
                    emb_lat_str,
                    self.stats["async_frames_replaced"],
                    worker_busy_pct,
                )

        except Exception as exc:
            logger.error("[Plugin:Face Matching] Unexpected error processing frame %d: %s", frame_idx, exc, exc_info=True)

        return events

    def _format_latencies(self, latencies: List[float]) -> str:
        """Helper to format avg/p95/max latency string."""
        if not latencies:
            return "avg:0.0ms, p95:0.0ms, max:0.0ms"
        arr = np.array(latencies[-100:], dtype=np.float32)
        avg_v = float(np.mean(arr))
        p95_v = float(np.percentile(arr, 95))
        max_v = float(np.max(arr))
        return f"avg:{avg_v:.1f}ms, p95:{p95_v:.1f}ms, max:{max_v:.1f}ms"

    def stop(self) -> None:
        """Stop plugin execution, release resources, and log final stats."""
        self.state = PluginState.STOPPING
        logger.info("[Plugin:Face Matching] Stopping...")

        # Terminate async worker thread if active
        if self._worker_thread is not None and self._worker_thread.is_alive():
            self._stop_event.set()
            self._input_event.set()
            self._worker_thread.join(timeout=2.0)
            if self._worker_thread.is_alive():
                logger.warning("[Plugin:Face Matching] Async inference worker thread did not stop within 2.0s timeout.")
            self._worker_thread = None

        with self._input_lock:
            self._pending_frame_data = None
        with self._output_lock:
            self._completed_events.clear()
            self._latest_face_overlays.clear()

        # Final shutdown stats line
        det_lat_str = self._format_latencies(self._detect_latencies_ms)
        emb_lat_str = self._format_latencies(self._embed_latencies_ms)
        logger.info(
            "[Plugin:Face Matching Shutdown Stats] Processed=%d | Detections=%d | Emitted=%d | Small=%d | LowQ=%d | BelowTh=%d | LowMargin=%d | DetectLatency=[%s] | EmbedLatency=[%s] | AsyncReplaced=%d",
            self.stats["frames_processed"],
            self.stats["faces_detected"],
            self.stats["events_emitted"],
            self.stats["skipped_too_small"],
            self.stats["skipped_low_quality"],
            self.stats["matched_below_threshold"],
            self.stats["rejected_low_margin"],
            det_lat_str,
            emb_lat_str,
            self.stats["async_frames_replaced"],
        )

        SharedFaceModelCache.get_instance().release()
        self.detector = None
        self.embedder = None
        self.gallery = None
        self.tracker = FaceIoUTracker()
        self._consensus_buffers.clear()

        self.state = PluginState.STOPPED
        logger.info("[Plugin:Face Matching] Stopped and models released.")

    def shutdown(self) -> None:
        self.stop()
