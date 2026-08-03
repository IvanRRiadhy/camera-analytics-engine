"""
Bounding-Box Data-Path Trace — Instrumented Live Pipeline Run.

Traces ONE tracked object's bounding box through every stage of the pipeline,
printing coordinates, format, and coordinate system at each stage.

Stages traced:
  1. YOLO raw output         (YOLOPoseAdapter._convert_results)
  2. Detection object        (DetectionService.process output)
  3. Tracker object           (TrackingService.process output)
  4. SharedAnalyticsContext   (ContextBuilder.build_context output)
  5. Builder input            (FramePresentationBuilder.build frame_context)
  6. PresentedBox constructor (FramePresentationBuilder.build -> PresentedBox)
  7. PresentationBuffer       (PresentationFrameBuffer.update)
  8. Renderer draw args       (OverlayRenderer.render -> cv2.rectangle)

DO NOT modify production code. This script monkeypatches at runtime for one trace pass.
"""

from __future__ import annotations

import logging
import os
import sys
import threading
import time
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("bbox_trace")

# ══════════════════════════════════════════════════════════════════════
# Trace state
# ══════════════════════════════════════════════════════════════════════
_trace_lock = threading.Lock()
_trace_done = threading.Event()
_stage_results: dict[str, dict] = {}
_traced_track_id: int | None = None
_frame_image_shape: tuple | None = None


def _record(stage_num: int, stage_name: str, track_id: Any, bbox_values: Any,
            bbox_format: str, coord_type: str, img_shape: tuple | None = None):
    """Record one stage's bbox snapshot."""
    entry = {
        "track_id": track_id,
        "bbox_values": bbox_values,
        "bbox_format": bbox_format,
        "coord_type": coord_type,
        "img_shape": img_shape,
    }
    key = f"Stage {stage_num}: {stage_name}"
    with _trace_lock:
        _stage_results[key] = entry
    logger.info(
        "[TRACE] %s | track_id=%s | bbox=%s | format=%s | coords=%s | img=%s",
        key, track_id, bbox_values, bbox_format, coord_type,
        f"{img_shape[1]}x{img_shape[0]}" if img_shape else "N/A"
    )


# ══════════════════════════════════════════════════════════════════════
# PHASE 1: Patch stages that don't cause circular imports
# ══════════════════════════════════════════════════════════════════════

# Stage 1: YOLO Raw Output
from camera_analytics.adapters.detection.yolo_pose_adapter import YOLOPoseAdapter

_orig_convert_results = YOLOPoseAdapter._convert_results
_stage1_done = False

def _patched_convert_results(self, yolo_results):
    global _stage1_done
    detections = _orig_convert_results(self, yolo_results)
    if not _stage1_done and detections and not _trace_done.is_set():
        det = detections[0]
        _stage1_done = True
        _record(1, "YOLO raw output", "N/A (pre-tracking)",
                [det.bbox.x1, det.bbox.y1, det.bbox.x2, det.bbox.y2],
                "xyxy (x1,y1,x2,y2)", "pixel", None)
    return detections

YOLOPoseAdapter._convert_results = _patched_convert_results


# Stage 2: DetectionService.process output
from camera_analytics.context.services import DetectionService

_orig_det_process = DetectionService.process
_stage2_done = False

def _patched_det_process(self, frame):
    global _stage2_done, _frame_image_shape
    detections, raw_result, elapsed_ms = _orig_det_process(self, frame)
    if not _stage2_done and detections and not _trace_done.is_set():
        _stage2_done = True
        if hasattr(frame, 'shape'):
            _frame_image_shape = frame.shape
        det = detections[0]
        if isinstance(det, dict):
            bbox = det.get("bbox", [0, 0, 0, 0])
            fmt = "xyxy in dict['bbox']"
        else:
            bbox = [det.bbox.x1, det.bbox.y1, det.bbox.x2, det.bbox.y2]
            fmt = "BoundingBox xyxy"
        _record(2, "DetectionService output", "N/A (pre-tracking)",
                list(bbox), fmt, "pixel", _frame_image_shape)
    return detections, raw_result, elapsed_ms

DetectionService.process = _patched_det_process


# Stage 3: TrackingService.process output
from camera_analytics.context.services import TrackingService

_orig_trk_process = TrackingService.process
_stage3_done = False

def _patched_trk_process(self, frame, detections, raw_det_result=None):
    global _stage3_done, _traced_track_id
    tracks, elapsed_ms = _orig_trk_process(self, frame, detections, raw_det_result)
    if not _stage3_done and tracks and not _trace_done.is_set():
        _stage3_done = True
        trk = tracks[0]
        if isinstance(trk, dict):
            t_id = trk.get("track_id", "?")
            bbox = trk.get("bbox", [0, 0, 0, 0])
            fmt = "xyxy in dict['bbox']"
        else:
            t_id = getattr(trk, "track_id", "?")
            bbox = [trk.bbox.x1, trk.bbox.y1, trk.bbox.x2, trk.bbox.y2]
            fmt = "BoundingBox xyxy"
        _traced_track_id = t_id
        _record(3, "TrackingService output", t_id, list(bbox), fmt, "pixel", _frame_image_shape)
    return tracks, elapsed_ms

TrackingService.process = _patched_trk_process


# Stage 4: SharedAnalyticsContext.tracks (after ContextBuilder)
from camera_analytics.context.services import ContextBuilder

_orig_build_context = ContextBuilder.build_context
_stage4_done = False

def _patched_build_context(self, *args, **kwargs):
    global _stage4_done
    ctx = _orig_build_context(self, *args, **kwargs)
    if not _stage4_done and ctx.tracks and not _trace_done.is_set():
        _stage4_done = True
        trk = ctx.tracks[0]
        if isinstance(trk, dict):
            t_id = trk.get("track_id", "?")
            bbox = trk.get("bbox", [0, 0, 0, 0])
            fmt = "xyxy list in dict['bbox']"
        else:
            t_id = getattr(trk, "track_id", "?")
            bbox = "unknown"
            fmt = "unknown"
        _record(4, "SharedAnalyticsContext.tracks", t_id,
                list(bbox) if isinstance(bbox, list) else bbox,
                fmt, "pixel", _frame_image_shape)
    return ctx

ContextBuilder.build_context = _patched_build_context


# ══════════════════════════════════════════════════════════════════════
# PHASE 2: Deferred patches for stages 5-8 (applied after engine boot)
# ══════════════════════════════════════════════════════════════════════
_stage5_done = False
_stage7_done = False
_stage8_done = False
_deferred_patched = False


def _apply_deferred_patches():
    """Patch viewer/builder/buffer/renderer AFTER the module graph is fully loaded."""
    global _deferred_patched
    if _deferred_patched:
        return
    _deferred_patched = True

    # Stage 5 & 6: FramePresentationBuilder.build
    from camera_analytics.viewer.builder import FramePresentationBuilder
    _orig_build = FramePresentationBuilder.build.__func__  # unwrap classmethod

    def _patched_build_inner(cls_arg, frame, camera, frame_context=None, summary=None,
                             metrics=None, gpu_id=0, queue_size=0):
        global _stage5_done
        if not _stage5_done and frame_context is not None and hasattr(frame_context, "tracks") and frame_context.tracks and not _trace_done.is_set():
            _stage5_done = True
            trk = frame_context.tracks[0]
            if isinstance(trk, dict):
                t_id = trk.get("track_id", "?")
                bbox = trk.get("bbox", [0, 0, 0, 0])
                _record(5, "Builder input (frame_context.tracks[0])", t_id,
                        list(bbox), "xyxy list in dict['bbox']", "pixel", _frame_image_shape)
            else:
                t_id = getattr(trk, "track_id", "?")
                bbox_obj = getattr(trk, "bbox", None)
                _record(5, "Builder input (frame_context.tracks[0])", t_id,
                        [bbox_obj.x1, bbox_obj.y1, bbox_obj.x2, bbox_obj.y2] if bbox_obj else "None",
                        "BoundingBox xyxy", "pixel", _frame_image_shape)

        presentation = _orig_build(cls_arg, frame, camera, frame_context, summary, metrics, gpu_id, queue_size)

        if not _trace_done.is_set() and presentation.boxes:
            box = presentation.boxes[0]
            img_shape = frame.image.shape if hasattr(frame, "image") and hasattr(frame.image, "shape") else _frame_image_shape
            _record(6, "PresentedBox constructor args", box.track_id,
                    [box.x1, box.y1, box.x2, box.y2],
                    "xyxy int fields (x1,y1,x2,y2)", "pixel", img_shape)

        return presentation

    FramePresentationBuilder.build = classmethod(_patched_build_inner)

    # Stage 7: PresentationFrameBuffer.update
    from camera_analytics.viewer.buffer import PresentationFrameBuffer
    _orig_buffer_update = PresentationFrameBuffer.update

    def _patched_buffer_update(self, presentation):
        global _stage7_done
        if not _stage7_done and presentation.boxes and not _trace_done.is_set():
            _stage7_done = True
            box = presentation.boxes[0]
            _record(7, "PresentationBuffer stored object", box.track_id,
                    [box.x1, box.y1, box.x2, box.y2],
                    "xyxy int fields (x1,y1,x2,y2)", "pixel",
                    presentation.image.shape if hasattr(presentation.image, "shape") else _frame_image_shape)
        _orig_buffer_update(self, presentation)

    PresentationFrameBuffer.update = _patched_buffer_update

    # Stage 8: OverlayRenderer.render
    from camera_analytics.viewer.renderer import OverlayRenderer
    _orig_render = OverlayRenderer.render

    def _patched_render(self, presentation):
        global _stage8_done
        if not _stage8_done and presentation.boxes and not _trace_done.is_set():
            _stage8_done = True
            box = presentation.boxes[0]
            canvas_shape = presentation.image.shape if hasattr(presentation.image, "shape") else None
            _record(8, "Renderer cv2.rectangle() args", box.track_id,
                    {"pt1": (box.x1, box.y1), "pt2": (box.x2, box.y2), "color": box.color_rgb},
                    "cv2.rectangle(canvas, pt1=(x1,y1), pt2=(x2,y2))", "pixel",
                    canvas_shape)
            _trace_done.set()
        return _orig_render(self, presentation)

    OverlayRenderer.render = _patched_render
    logger.info("[TRACE] Deferred patches for Stages 5-8 applied successfully.")


# ══════════════════════════════════════════════════════════════════════
# Boot the real engine and run
# ══════════════════════════════════════════════════════════════════════
def _print_report():
    """Print the final bounding-box trace report."""
    print()
    print("=" * 100)
    print("BOUNDING-BOX DATA-PATH TRACE RESULTS")
    print("=" * 100)
    print()

    if _frame_image_shape:
        h, w = _frame_image_shape[0], _frame_image_shape[1]
        print(f"  Frame image dimensions: {w}x{h} pixels (width x height)")
        print()

    corruption_found = False
    first_corruption_stage = None
    prev_bbox = None

    for stage_key in sorted(_stage_results.keys()):
        entry = _stage_results[stage_key]
        print(f"  {stage_key}")
        print(f"    track_id:    {entry['track_id']}")
        print(f"    bbox:        {entry['bbox_values']}")
        print(f"    format:      {entry['bbox_format']}")
        print(f"    coord_type:  {entry['coord_type']}")
        if entry['img_shape']:
            h, w = entry['img_shape'][0], entry['img_shape'][1]
            print(f"    image:       {w}x{h}")

        bbox = entry['bbox_values']
        if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
            all_small = all(isinstance(v, (int, float)) and 0 <= v <= 1.0 for v in bbox)
            any_large = any(isinstance(v, (int, float)) and v > 1.0 for v in bbox)
            if all_small and not any_large:
                print(f"    ⚠ WARNING: bbox values are all in [0, 1] — likely NORMALIZED, not pixel!")
                if not corruption_found:
                    corruption_found = True
                    first_corruption_stage = stage_key
                    print(f"    ★ FIRST CORRUPTION POINT ★")

            if any_large and entry['img_shape']:
                x1, y1, x2, y2 = bbox
                w_img, h_img = entry['img_shape'][1], entry['img_shape'][0]
                if isinstance(x2, (int, float)) and isinstance(y2, (int, float)):
                    if x2 > w_img or y2 > h_img:
                        print(f"    ⚠ WARNING: bbox exceeds image bounds ({w_img}x{h_img})!")

            if bbox == [100.0, 150.0, 250.0, 400.0] or bbox == [100, 150, 250, 400]:
                print(f"    ⚠ WARNING: bbox matches HARDCODED FALLBACK from DetectionService!")
                if not corruption_found:
                    corruption_found = True
                    first_corruption_stage = stage_key
                    print(f"    ★ FIRST CORRUPTION POINT ★")

        if prev_bbox is not None and isinstance(bbox, (list, tuple)):
            if isinstance(prev_bbox, (list, tuple)) and len(prev_bbox) == 4 and len(bbox) == 4:
                if [float(a) for a in prev_bbox] != [float(a) for a in bbox]:
                    print(f"    ⚠ VALUES CHANGED from previous stage: {prev_bbox} → {bbox}")
                    if not corruption_found:
                        corruption_found = True
                        first_corruption_stage = stage_key
                        print(f"    ★ FIRST CORRUPTION POINT ★")

        if isinstance(bbox, (list, tuple)):
            prev_bbox = bbox
        print()

    print("=" * 100)
    if not _stage_results:
        print("  ⚠ NO STAGES WERE TRACED. The pipeline may not have processed any detections.")
    elif corruption_found:
        print(f"  ✗ CORRUPTION DETECTED at: {first_corruption_stage}")
    else:
        print("  ✓ No coordinate corruption detected. Bbox values are consistent pixel coords at all stages.")
    print("=" * 100)


def _watcher_thread():
    """Background thread that waits for trace completion and then prints results + exits."""
    completed = _trace_done.wait(timeout=20.0)
    if not completed:
        logger.warning("Trace did not complete within 20 seconds. Printing partial results.")
    _print_report()
    os._exit(0)


def main():
    logger.info("=" * 80)
    logger.info("BOUNDING-BOX DATA-PATH TRACE — LIVE PIPELINE")
    logger.info("=" * 80)

    # Import engine first to fully resolve the module graph (avoids circular import)
    from camera_analytics.main import main as engine_main

    # Now apply deferred patches (module graph is fully loaded)
    _apply_deferred_patches()

    # Start watcher in background (will print report and force exit)
    watcher = threading.Thread(target=_watcher_thread, daemon=True)
    watcher.start()

    # Run engine in MAIN thread (required for signal.signal() to work)
    # Set headless mode and pass a max run duration
    sys.argv = ["trace_bbox.py", "--headless"]
    try:
        engine_main(max_run_sec=15.0)
    except SystemExit:
        pass
    except Exception as e:
        logger.error("Engine exception: %s", e)
    finally:
        if not _trace_done.is_set():
            _trace_done.set()
        time.sleep(0.5)
        _print_report()
        os._exit(0)


if __name__ == "__main__":
    main()
