from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from camera_analytics.events.models import BaseRuntimeEvent
from camera_analytics.plugins.framework.context import PluginContext
from camera_analytics.plugins.framework.states import PluginState
from camera_analytics.sdk.base_plugin import BaseAnalyticsPlugin

from camera_analytics.plugins.vehicle_lpr.config import VehicleLPRConfig
from camera_analytics.plugins.vehicle_lpr.localizer import PlateLocalizer
from camera_analytics.plugins.vehicle_lpr.model_cache import SharedModelCache
from camera_analytics.plugins.vehicle_lpr.tracker import PlateIoUTracker

logger = logging.getLogger(__name__)


class VehicleLPRPlugin(BaseAnalyticsPlugin):
    """Production-grade Vehicle License Plate Recognition (LPR) Vision Plugin."""

    def __init__(self, name: str = "Vehicle LPR", version: str = "1.0.0") -> None:
        super().__init__(name=name, version=version, description="Indonesian Vehicle License Plate Recognition (LPR)")
        self.config = VehicleLPRConfig()
        self.localizer: PlateLocalizer = PlateLocalizer(mode=self.config.mode, roi=self.config.roi)
        self.tracker = PlateIoUTracker()
        self.detector = None
        self.reader = None

        # Per-pipeline voting and cooldown state
        self._voting_engines: Dict[int, Any] = {}          # track_id -> PlainCountVotingEngine
        self._cooldown_map: Dict[str, float] = {}          # plate_text -> last_emitted_timestamp
        self._logged_frame_shape = False
        self._last_stats_log_time = 0.0

        # Reconciled counters for exact bucket accounting (mutually exclusive partition of detections_total)
        self.stats = {
            "detections_total": 0,
            "skipped_too_small": 0,
            "skipped_too_blurry": 0,
            "skipped_too_dark": 0,
            "skipped_lock_timeout": 0,
            "skipped_after_consensus": 0,
            "reader_no_read": 0,
            "reader_ok": 0,
            # Sub-counters / secondary metrics outside the detections_total sum:
            "skipped_cooldown": 0,
            "events_emitted": 0,
            "stride_skipped_frames": 0,
            "frames_without_detection": 0,
            "detected_widths": [],
            "normalized_sharpness": [],
            "raw_sharpness": [],
        }
        self._process_latencies: List[float] = []
        self._slowest_calls: List[Dict[str, Any]] = []
        self.last_assigned_track_id: Optional[int] = None

    def initialize(self, context: PluginContext) -> bool:
        self.context = context
        pipeline_id = getattr(context, "pipeline_id", "pipeline_default")
        logger.info("[Plugin:Vehicle LPR] Initializing in pipeline '%s'...", pipeline_id)

        # Merge configuration from PluginContext.config or context.pipeline_config if available
        raw_cfg = getattr(context, "config", {})
        if isinstance(raw_cfg, dict):
            # Check module_settings or vehicle_lpr block
            mod_cfg = raw_cfg.get("vehicle_lpr", raw_cfg)
            if isinstance(mod_cfg, dict):
                self.config = VehicleLPRConfig.from_dict(mod_cfg)

        self.localizer = PlateLocalizer(mode=self.config.mode, roi=self.config.roi)
        self.tracker = PlateIoUTracker(max_lost_strides=10)

        # Log ONE line with the effective configuration (Item 2)
        det_basename = os.path.basename(self.config.detector_weights) if self.config.detector_weights else "none"
        rdr_basename = os.path.basename(self.config.reader_weights) if self.config.reader_weights else "none"
        logger.info(
            "[Plugin:Vehicle LPR] Effective Config [pipeline: %s]: mode=%s, det_weights=%s (imgsz=%d, conf=%.2f), rdr_weights=%s (imgsz=%d, conf=%.2f), stride=%d, min_width=%.0fpx, min_sharp=%.1f (ref_w=%d), min_votes=%d, min_share=%.2f, cooldown=%.1fs, lock_timeout=%.2fs",
            pipeline_id,
            self.config.mode,
            det_basename,
            self.config.detector_imgsz,
            self.config.detector_conf,
            rdr_basename,
            self.config.reader_imgsz,
            self.config.reader_conf,
            self.config.frame_stride,
            self.config.min_plate_width_px,
            self.config.min_sharpness,
            self.config.sharpness_ref_width,
            self.config.min_observations,
            self.config.min_winner_share,
            self.config.cooldown_s,
            self.config.lock_timeout_s,
        )

        # Acquire cached detector and reader models
        try:
            if self.config.mode == "detector":
                self.detector = SharedModelCache.get_detector(
                    weights=self.config.detector_weights,
                    device=self.config.device,
                    imgsz=self.config.detector_imgsz,
                    conf=self.config.detector_conf,
                )

            self.reader = SharedModelCache.get_reader(
                weights=self.config.reader_weights,
                device=self.config.device,
                imgsz=self.config.reader_imgsz,
                conf=self.config.reader_conf,
                expected_sha256=self.config.expected_sha256,
                config_path=self.config.reader_config_path,
            )
        except Exception as exc:
            logger.error("[Plugin:Vehicle LPR] Failed to initialize models in pipeline '%s': %s", pipeline_id, exc)
            # Ensure any partial refcounts are cleaned up
            self.shutdown()
            self.state = PluginState.FAILED
            return False

        self.state = PluginState.INITIALIZED
        logger.info("[Plugin:Vehicle LPR] Initialized successfully in pipeline '%s'.", pipeline_id)
        return True

    def warmup(self) -> bool:
        if self.state == PluginState.FAILED:
            return False
        self.state = PluginState.WARMUP
        logger.info("[Plugin:Vehicle LPR] Executing tensor warmup...")
        try:
            dummy_crop = np.zeros((64, 180, 3), dtype=np.uint8)
            with SharedModelCache.reader_inference_lock:
                _ = self.reader.read(dummy_crop)

            if self.config.mode == "detector" and self.detector is not None:
                dummy_frame = np.zeros((640, 640, 3), dtype=np.uint8)
                with SharedModelCache.detector_inference_lock:
                    _ = self.detector.predict(dummy_frame, imgsz=640, device=self.config.device, verbose=False)

            logger.info("[Plugin:Vehicle LPR] Warmup complete.")
            return True
        except Exception as exc:
            logger.warning("[Plugin:Vehicle LPR] Warmup encountered error (continuing): %s", exc)
            return True

    def start(self) -> None:
        if self.state == PluginState.FAILED:
            logger.warning("[Plugin:Vehicle LPR] Cannot start plugin in FAILED state.")
            return
        super().start()

    def _build_lpr_event(
        self,
        context: Any,
        plate_str: str,
        plate_conf: float,
        tid: int,
        voting_res: Any,
        track_bbox: Tuple[float, float, float, float],
        frame_shape: Tuple[int, int],
        crop: Optional[np.ndarray],
        track_conf: float,
        now_ts: float,
        finalized_on_expiry: bool = False,
        crop_sharpness: Optional[float] = None,
    ) -> BaseRuntimeEvent:
        h, w = frame_shape
        bx1, by1, bx2, by2 = track_bbox
        norm_box = [
            float(round(bx1 / w, 4)),
            float(round(by1 / h, 4)),
            float(round(bx2 / w, 4)),
            float(round(by2 / h, 4)),
        ]

        best = voting_res.best_reading or {}
        char_confs = [float(c) for c in best.get("char_box_confs", [])]
        attributes = {
            "plate_text": plate_str,
            "status": str(voting_res.status),
            "winner_share": float(voting_res.winner_share),
            "observation_count": int(voting_res.total_votes),
            "char_confidences": char_confs,
            "plate_detector_confidence": float(track_conf),
        }
        if crop_sharpness is not None:
            attributes["sharpness"] = float(round(crop_sharpness, 2))
        if finalized_on_expiry:
            attributes["finalized_on_expiry"] = True

        snapshot_path = None
        if self.config.save_snapshots and self.config.snapshot_dir and crop is not None and crop.size > 0:
            try:
                s_dir = Path(self.config.snapshot_dir)
                s_dir.mkdir(parents=True, exist_ok=True)
                cam_id = getattr(context, "camera_id", "cam_default")
                snap_filename = f"{cam_id}_{plate_str}_{int(now_ts * 1000)}.jpg"
                snap_path_obj = s_dir / snap_filename
                temp_snap = s_dir / f".tmp_{snap_filename}"
                cv2.imwrite(str(temp_snap), crop)
                temp_snap.replace(snap_path_obj)
                snapshot_path = str(snap_path_obj)
            except Exception as snap_exc:
                logger.warning("[Plugin:Vehicle LPR] Snapshot write failed: %s", snap_exc)

        return BaseRuntimeEvent(
            camera_id=str(getattr(context, "camera_id", "cam_default")),
            pipeline_assignment_id=str(getattr(context, "pipeline_id", "pipeline_default")),
            plugin_name="Vehicle LPR",
            event_type="VEHICLE_LPR",
            confidence=plate_conf,
            track_id=int(tid),
            bounding_box=norm_box,
            snapshot_path=snapshot_path,
            attributes=attributes,
        )

    def process(self, context: Any) -> List[BaseRuntimeEvent]:
        """Process unified frame context and emit verified Vehicle LPR runtime events."""
        if self.state != PluginState.RUNNING:
            return []

        frame = getattr(context, "frame", None)
        if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
            return []

        if not self._logged_frame_shape:
            pipe_id = getattr(self.context, "pipeline_id", "default")
            cam_id = getattr(self.context, "camera_id", "default")
            logger.info(
                "[Plugin:Vehicle LPR] First process() call [%s | %s]: context.frame.shape = %s (H=%d, W=%d, C=%d)",
                pipe_id, cam_id, frame.shape, frame.shape[0], frame.shape[1], frame.shape[2] if frame.ndim > 2 else 1
            )
            self._logged_frame_shape = True

        t_proc_start = time.perf_counter()
        frame_idx = int(getattr(context, "frame_index", 0))
        now_ts = float(getattr(context, "timestamp_utc", time.time()))
        h, w = frame.shape[:2]

        events: List[BaseRuntimeEvent] = []

        # Granular latency breakdown (ms) for this call
        call_timings = {
            "frame_idx": frame_idx,
            "detector_lock_wait_ms": 0.0,
            "detector_infer_ms": 0.0,
            "crop_quality_ms": 0.0,
            "reader_lock_wait_ms": 0.0,
            "reader_infer_ms": 0.0,
            "total_ms": 0.0,
        }

        try:
            # 1. Evaluate frame stride
            is_detector_turn = (frame_idx % max(1, self.config.frame_stride)) == 0
            if not is_detector_turn:
                self.stats["stride_skipped_frames"] += 1

            # 2. Plate Localization
            detections = []
            if is_detector_turn:
                t0_det_wait = time.perf_counter()
                acquired_det = SharedModelCache.detector_inference_lock.acquire(timeout=self.config.lock_timeout_s)
                call_timings["detector_lock_wait_ms"] = round((time.perf_counter() - t0_det_wait) * 1000.0, 3)
                if not acquired_det:
                    self.stats["skipped_lock_timeout"] += 1
                    return []
                try:
                    t0_det_inf = time.perf_counter()
                    detections = self.localizer.localize(
                        frame=frame,
                        detector=self.detector,
                        conf=self.config.detector_conf,
                        iou=self.config.detector_iou,
                        imgsz=self.config.detector_imgsz,
                        device=self.config.device,
                    )
                    call_timings["detector_infer_ms"] = round((time.perf_counter() - t0_det_inf) * 1000.0, 3)
                finally:
                    SharedModelCache.detector_inference_lock.release()

                if not detections:
                    self.stats["frames_without_detection"] += 1

            # 3. Update spatial tracker
            expired_tracks: List[Any] = []
            if is_detector_turn:
                tracks_updated, expired_tracks = self.tracker.update(detections, frame_idx)
                self.stats["detections_total"] += len(detections)
            else:
                tracks_updated = [(t, False) for t in self.tracker.tracks.values()]

            # 3b. Check expired tracks for expiry emission
            if self.config.emit_on_track_expiry and expired_tracks:
                for exp_t in expired_tracks:
                    exp_tid = exp_t.track_id
                    if exp_t.has_emitted:
                        if exp_tid in self._voting_engines:
                            del self._voting_engines[exp_tid]
                        continue

                    if exp_tid in self._voting_engines:
                        v_engine = self._voting_engines[exp_tid]
                        v_res = v_engine.compute_consensus()
                        if (
                            v_res.plate_text
                            and v_res.total_votes >= self.config.min_observations
                            and (v_res.status == "GRAMMAR_VALID" or (self.config.allow_review and v_res.status == "REVIEW"))
                        ):
                            plate_str = str(v_res.plate_text).strip().upper()
                            last_seen = self._cooldown_map.get(plate_str, 0.0)
                            if (now_ts - last_seen) >= self.config.cooldown_s:
                                best = v_res.best_reading or {}
                                plate_conf = float(best.get("mean_box_conf_all", 0.90))
                                exp_evt = self._build_lpr_event(
                                    context=context,
                                    plate_str=plate_str,
                                    plate_conf=plate_conf,
                                    tid=exp_tid,
                                    voting_res=v_res,
                                    track_bbox=exp_t.bbox,
                                    frame_shape=(h, w),
                                    crop=None,
                                    track_conf=exp_t.conf,
                                    now_ts=now_ts,
                                    finalized_on_expiry=True,
                                    crop_sharpness=None,
                                )
                                events.append(exp_evt)
                                self.stats["events_emitted"] += 1
                                self._cooldown_map[plate_str] = now_ts
                                exp_t.has_emitted = True
                                logger.info(
                                    "[Plugin:Vehicle LPR] Emitted EXPIRY Plate: '%s' | Conf: %.3f | Votes: %d | Track: %d",
                                    plate_str, plate_conf, v_res.total_votes, exp_tid
                                )
                        del self._voting_engines[exp_tid]

            # 4. Process each active track
            for track, is_new_or_updated in tracks_updated:
                if not is_new_or_updated:
                    continue

                tid = track.track_id
                self.last_assigned_track_id = tid

                # If track already emitted consensus, skip further OCR
                if track.has_emitted:
                    self.stats["skipped_after_consensus"] += 1
                    continue

                # Instantiate voting engine for this track if needed
                if tid not in self._voting_engines:
                    from anpr_v2.voting import PlainCountVotingEngine
                    self._voting_engines[tid] = PlainCountVotingEngine(min_votes_for_consensus=self.config.min_observations)

                engine = self._voting_engines[tid]

                t0_crop_qual = time.perf_counter()
                # Crop plate
                crop, (cx1, cy1, cx2, cy2) = PlateLocalizer.crop_plate(
                    frame, track.bbox, self.config.pad_ratio_x, self.config.pad_ratio_y
                )

                if crop.size == 0:
                    self.stats["skipped_too_small"] += 1
                    call_timings["crop_quality_ms"] += (time.perf_counter() - t0_crop_qual) * 1000.0
                    continue

                cw = float(cx2 - cx1)
                self.stats["detected_widths"].append(cw)
                if len(self.stats["detected_widths"]) > 200:
                    self.stats["detected_widths"].pop(0)

                # Quality filter: minimum width
                if cw < self.config.min_plate_width_px:
                    self.stats["skipped_too_small"] += 1
                    call_timings["crop_quality_ms"] += (time.perf_counter() - t0_crop_qual) * 1000.0
                    continue

                gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

                # Quality filter: normalized sharpness (resized to fixed width)
                ref_w = max(32, int(self.config.sharpness_ref_width))
                ref_h = max(16, int(round(gray.shape[0] * (ref_w / max(1, gray.shape[1])))))
                resized_gray = cv2.resize(gray, (ref_w, ref_h), interpolation=cv2.INTER_AREA)
                sharpness = float(cv2.Laplacian(resized_gray, cv2.CV_64F).var())
                raw_sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())

                self.stats["normalized_sharpness"].append(sharpness)
                if len(self.stats["normalized_sharpness"]) > 200:
                    self.stats["normalized_sharpness"].pop(0)

                self.stats["raw_sharpness"].append(raw_sharpness)
                if len(self.stats["raw_sharpness"]) > 200:
                    self.stats["raw_sharpness"].pop(0)

                # Optional debug crop logging (strictly gated off in normal production runs)
                debug_csv_path = self.config.debug_crop_csv or os.environ.get("ANPR_DEBUG_CROP_CSV")
                if debug_csv_path:
                    try:
                        import csv
                        os.makedirs(os.path.dirname(os.path.abspath(debug_csv_path)), exist_ok=True)
                        write_header = not os.path.exists(debug_csv_path)
                        with open(debug_csv_path, "a", newline="") as ef:
                            cw_writer = csv.writer(ef)
                            if write_header:
                                cw_writer.writerow(["timestamp", "pipeline_id", "frame_idx", "track_id", "crop_w", "norm_sharpness", "raw_sharpness", "min_sharpness_passed"])
                            cw_writer.writerow([round(now_ts, 3), getattr(self.context, "pipeline_id", "default"), frame_idx, tid, round(cw, 1), round(sharpness, 2), round(raw_sharpness, 2), sharpness >= self.config.min_sharpness])
                    except Exception:
                        pass

                if sharpness < self.config.min_sharpness:
                    self.stats["skipped_too_blurry"] += 1
                    call_timings["crop_quality_ms"] += (time.perf_counter() - t0_crop_qual) * 1000.0
                    logger.debug(
                        "[Plugin:Vehicle LPR] Track %d crop rejected: sharpness=%.2f < min_sharpness=%.2f (w=%.0f)",
                        tid, sharpness, self.config.min_sharpness, cw
                    )
                    continue

                mean_brightness = float(np.mean(gray))
                if mean_brightness < self.config.min_brightness or mean_brightness > self.config.max_brightness:
                    self.stats["skipped_too_dark"] += 1
                    call_timings["crop_quality_ms"] += (time.perf_counter() - t0_crop_qual) * 1000.0
                    logger.debug(
                        "[Plugin:Vehicle LPR] Track %d crop rejected: brightness=%.2f not in [%.1f, %.1f]",
                        tid, mean_brightness, self.config.min_brightness, self.config.max_brightness
                    )
                    continue

                call_timings["crop_quality_ms"] += (time.perf_counter() - t0_crop_qual) * 1000.0

                # Execute Character Reader with inference lock
                t0_rdr_wait = time.perf_counter()
                acquired_reader = SharedModelCache.reader_inference_lock.acquire(timeout=self.config.lock_timeout_s)
                call_timings["reader_lock_wait_ms"] += (time.perf_counter() - t0_rdr_wait) * 1000.0
                if not acquired_reader:
                    self.stats["skipped_lock_timeout"] += 1
                    continue
                try:
                    t0_rdr_inf = time.perf_counter()
                    reader_out = self.reader.read(crop)
                    call_timings["reader_infer_ms"] += (time.perf_counter() - t0_rdr_inf) * 1000.0
                finally:
                    SharedModelCache.reader_inference_lock.release()

                if reader_out.status == "NO_READ" or not reader_out.raw_text:
                    self.stats["reader_no_read"] += 1
                    continue

                self.stats["reader_ok"] += 1

                # Add observation to temporal voting pool
                engine.add_observation(
                    reader_output=reader_out,
                    plate_width=cw,
                    sharpness=sharpness,
                    timestamp=now_ts,
                )

                # Check for consensus: strict winner_share > min_winner_share and >= min_observations
                voting_res = engine.compute_consensus()
                should_emit = False

                if (
                    voting_res.plate_text
                    and voting_res.total_votes >= self.config.min_observations
                    and voting_res.winner_share > self.config.min_winner_share
                ):
                    if voting_res.status == "GRAMMAR_VALID" or (self.config.allow_review and voting_res.status == "REVIEW"):
                        should_emit = True

                if should_emit and voting_res.plate_text:
                    plate_str = str(voting_res.plate_text).strip().upper()

                    # Cooldown deduplication check
                    last_seen = self._cooldown_map.get(plate_str, 0.0)
                    if (now_ts - last_seen) < self.config.cooldown_s:
                        self.stats["skipped_cooldown"] += 1
                        track.has_emitted = True
                        continue

                    best = voting_res.best_reading or {}
                    plate_conf = float(best.get("mean_box_conf_all", 0.90))

                    event = self._build_lpr_event(
                        context=context,
                        plate_str=plate_str,
                        plate_conf=plate_conf,
                        tid=tid,
                        voting_res=voting_res,
                        track_bbox=track.bbox,
                        frame_shape=(h, w),
                        crop=crop,
                        track_conf=track.conf,
                        now_ts=now_ts,
                        finalized_on_expiry=False,
                        crop_sharpness=sharpness,
                    )

                    events.append(event)
                    self.stats["events_emitted"] += 1
                    self._cooldown_map[plate_str] = now_ts
                    track.has_emitted = True
                    logger.info(
                        "[Plugin:Vehicle LPR] Emitted VEHICLE_LPR Plate: '%s' | Conf: %.3f | WinnerShare: %.2f | Track: %d",
                        plate_str, plate_conf, voting_res.winner_share, tid
                    )

            # 5. Periodic rate-limited status log
            if now_ts - self._last_stats_log_time >= 10.0:
                self._last_stats_log_time = now_ts
                widths = self.stats["detected_widths"]
                w_summary = f"W(min/med/max)={min(widths):.0f}/{float(np.median(widths)):.0f}/{max(widths):.0f}" if widths else "W=None"
                logger.info(
                    "[Plugin:Vehicle LPR] Stats [pipeline: %s]: TotalDet=%d, ReadOk=%d, Emitted=%d, %s | Skips: Small=%d, Blur=%d, Dark=%d, Consensus=%d, Cooldown=%d, Lock=%d, NoRead=%d",
                    getattr(self.context, "pipeline_id", "default"),
                    self.stats["detections_total"], self.stats["reader_ok"], self.stats["events_emitted"],
                    w_summary, self.stats["skipped_too_small"], self.stats["skipped_too_blurry"], self.stats["skipped_too_dark"],
                    self.stats["skipped_after_consensus"], self.stats["skipped_cooldown"], self.stats["skipped_lock_timeout"],
                    self.stats["reader_no_read"]
                )

        except Exception as exc:
            logger.error("[Plugin:Vehicle LPR] Error during frame process in '%s': %s", getattr(self.context, "pipeline_id", "default"), exc, exc_info=True)

        finally:
            t_proc_ms = (time.perf_counter() - t_proc_start) * 1000.0
            call_timings["total_ms"] = round(t_proc_ms, 3)
            call_timings["crop_quality_ms"] = round(call_timings["crop_quality_ms"], 3)
            call_timings["reader_lock_wait_ms"] = round(call_timings["reader_lock_wait_ms"], 3)
            call_timings["reader_infer_ms"] = round(call_timings["reader_infer_ms"], 3)

            self._process_latencies.append(t_proc_ms)
            if len(self._process_latencies) > 2000:
                self._process_latencies.pop(0)

            # Maintain top 5 slowest calls
            self._slowest_calls.append(call_timings)
            self._slowest_calls.sort(key=lambda x: x["total_ms"], reverse=True)
            if len(self._slowest_calls) > 5:
                self._slowest_calls.pop()

        return events

    def get_stats(self) -> Dict[str, Any]:
        """Expose operational skip and health metrics."""
        res = dict(self.stats)
        if self._process_latencies:
            lats = sorted(self._process_latencies)
            res["process_ms_avg"] = round(float(np.mean(lats)), 2)
            res["process_ms_p95"] = round(float(np.percentile(lats, 95)), 2)
            res["process_ms_p99"] = round(float(np.percentile(lats, 99)), 2)
            res["process_ms_max"] = round(float(max(lats)), 2)
        else:
            res["process_ms_avg"] = 0.0
            res["process_ms_p95"] = 0.0
            res["process_ms_p99"] = 0.0
            res["process_ms_max"] = 0.0

        for key, out_name in [
            ("detected_widths", "plate_width_px"),
            ("normalized_sharpness", "normalized_sharpness"),
            ("raw_sharpness", "raw_sharpness"),
        ]:
            vals = self.stats.get(key, [])
            if vals:
                res[f"{out_name}_min"] = round(float(min(vals)), 2)
                res[f"{out_name}_median"] = round(float(np.median(vals)), 2)
                res[f"{out_name}_max"] = round(float(max(vals)), 2)
            else:
                res[f"{out_name}_min"] = 0.0
                res[f"{out_name}_median"] = 0.0
                res[f"{out_name}_max"] = 0.0

        res["slowest_calls"] = list(self._slowest_calls)
        return res

    def stop(self) -> None:
        self.state = PluginState.STOPPING
        pipe_id = getattr(self.context, "pipeline_id", "default")
        stats_dict = self.get_stats()
        logger.info(
            "[Plugin:Vehicle LPR] Shutdown Stats [%s]: TotalDet=%d, ReadOk=%d, Emitted=%d | Widths: min=%.1f, med=%.1f, max=%.1f | NormSharp: min=%.1f, med=%.1f, max=%.1f | RawSharp: min=%.1f, med=%.1f, max=%.1f | Latencies: avg=%.2fms, p95=%.2fms, max=%.2fms | Skips: Small=%d, Blur=%d, Dark=%d, Consensus=%d, Lock=%d, NoRead=%d | CooldownSuppressed=%d",
            pipe_id,
            stats_dict.get("detections_total", 0),
            stats_dict.get("reader_ok", 0),
            stats_dict.get("events_emitted", 0),
            stats_dict.get("plate_width_px_min", 0.0),
            stats_dict.get("plate_width_px_median", 0.0),
            stats_dict.get("plate_width_px_max", 0.0),
            stats_dict.get("normalized_sharpness_min", 0.0),
            stats_dict.get("normalized_sharpness_median", 0.0),
            stats_dict.get("normalized_sharpness_max", 0.0),
            stats_dict.get("raw_sharpness_min", 0.0),
            stats_dict.get("raw_sharpness_median", 0.0),
            stats_dict.get("raw_sharpness_max", 0.0),
            stats_dict.get("process_ms_avg", 0.0),
            stats_dict.get("process_ms_p95", 0.0),
            stats_dict.get("process_ms_max", 0.0),
            stats_dict.get("skipped_too_small", 0),
            stats_dict.get("skipped_too_blurry", 0),
            stats_dict.get("skipped_too_dark", 0),
            stats_dict.get("skipped_after_consensus", 0),
            stats_dict.get("skipped_lock_timeout", 0),
            stats_dict.get("reader_no_read", 0),
            stats_dict.get("skipped_cooldown", 0),
        )
        self._voting_engines.clear()
        self._cooldown_map.clear()
        self.tracker.reset()
        self.state = PluginState.STOPPED

    def shutdown(self) -> None:
        self.stop()
        logger.info("[Plugin:Vehicle LPR] Shutting down resources for pipeline '%s'...", getattr(self.context, "pipeline_id", "default"))
        if self.config.mode == "detector" and self.detector is not None:
            SharedModelCache.release_detector()
            self.detector = None
        if self.reader is not None:
            SharedModelCache.release_reader()
            self.reader = None
        logger.info("[Plugin:Vehicle LPR] Shutdown complete.")
