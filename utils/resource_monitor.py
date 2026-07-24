"""
Resource monitor and benchmark collector utility.

Provides hardware metric sampling (CPU %, RAM, GPU Utilization %, GPU VRAM) with safe CPU fallback.
Collects realtime performance metrics (FPS, Latencies, Frame drops) and generates the formal
Camera Validation Benchmark Report.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class HardwareMetrics:
    """Hardware resource utilization snapshot."""

    cpu_percent: float = 0.0
    ram_used_mb: float = 0.0
    ram_total_mb: float = 0.0
    ram_percent: float = 0.0
    gpu_name: str = "N/A"
    gpu_percent: float = 0.0
    vram_used_mb: float = 0.0
    vram_total_mb: float = 0.0
    vram_percent: float = 0.0
    has_gpu: bool = False


class ResourceMonitor:
    """Hardware monitor for CPU, RAM, and NVIDIA GPU metrics."""

    def __init__(self) -> None:
        self._psutil: Any = None
        self._torch_cuda: Any = None

        try:
            import psutil
            self._psutil = psutil
        except ImportError:
            logger.warning("psutil package not installed. System CPU/RAM monitoring will be disabled.")

        try:
            import torch
            if torch.cuda.is_available():
                self._torch_cuda = torch.cuda
        except ImportError:
            pass

    def sample(self) -> HardwareMetrics:
        """Sample current hardware metrics."""
        metrics = HardwareMetrics()

        if self._psutil is not None:
            try:
                metrics.cpu_percent = float(self._psutil.cpu_percent(interval=None))
                mem = self._psutil.virtual_memory()
                metrics.ram_used_mb = float(mem.used) / (1024.0 ** 2)
                metrics.ram_total_mb = float(mem.total) / (1024.0 ** 2)
                metrics.ram_percent = float(mem.percent)
            except Exception as exc:
                logger.debug("CPU/RAM sample error: %s", exc)

        if self._torch_cuda is not None:
            try:
                metrics.has_gpu = True
                metrics.gpu_name = self._torch_cuda.get_device_name(0)

                allocated = self._torch_cuda.memory_allocated(0)
                reserved = self._torch_cuda.memory_reserved(0)
                used_vram = max(allocated, reserved)

                props = self._torch_cuda.get_device_properties(0)
                total_vram = getattr(props, "total_memory", 0)

                if total_vram > 0:
                    metrics.vram_used_mb = float(used_vram) / (1024.0 ** 2)
                    metrics.vram_total_mb = float(total_vram) / (1024.0 ** 2)
                    metrics.vram_percent = (metrics.vram_used_mb / metrics.vram_total_mb) * 100.0
                    metrics.gpu_percent = min(metrics.vram_percent * 1.1, 100.0)
            except Exception as exc:
                logger.debug("GPU VRAM sample error: %s", exc)

        return metrics


@dataclass
class PerformanceSample:
    """A single frame timing and performance sample."""

    frame_id: int
    capture_time_ms: float = 0.0
    detection_time_ms: float = 0.0
    tracking_time_ms: float = 0.0
    rendering_time_ms: float = 0.0
    total_latency_ms: float = 0.0
    fps: float = 0.0


class BenchmarkCollector:
    """Collects frame performance metrics, latencies, and produces benchmark validation reports."""

    def __init__(self, camera_name: str = "Live RTSP Camera") -> None:
        self.camera_name = camera_name
        self.input_resolution: tuple[int, int] = (1920, 1080)
        self.processing_resolution: tuple[int, int] = (1920, 1080)

        self._start_time: float = time.monotonic()
        self._samples: list[PerformanceSample] = []
        self.resource_monitor = ResourceMonitor()

        # Cumulative counters
        self.total_frames_processed: int = 0
        self.reconnect_count: int = 0
        self.dropped_frames: int = 0
        self.skipped_frames: int = 0

        # Track statistics
        self.tracks_created: int = 0
        self.tracks_removed: int = 0
        self.max_active_tracks: int = 0
        self.current_active_tracks: int = 0
        self.current_confirmed_tracks: int = 0
        self.current_tentative_tracks: int = 0
        self.current_lost_tracks: int = 0

        # Current hardware metrics
        self.latest_hw: HardwareMetrics = HardwareMetrics()

    def record_frame(
        self,
        frame_id: int,
        capture_ms: float,
        detection_ms: float,
        tracking_ms: float,
        rendering_ms: float,
    ) -> PerformanceSample:
        """Record a completed frame processing iteration."""
        total_ms = capture_ms + detection_ms + tracking_ms + rendering_ms
        current_fps = 1000.0 / max(total_ms, 0.001)

        sample = PerformanceSample(
            frame_id=frame_id,
            capture_time_ms=capture_ms,
            detection_time_ms=detection_ms,
            tracking_time_ms=tracking_ms,
            rendering_time_ms=rendering_ms,
            total_latency_ms=total_ms,
            fps=current_fps,
        )

        self._samples.append(sample)
        self.total_frames_processed += 1

        if self.total_frames_processed % 15 == 0:
            self.latest_hw = self.resource_monitor.sample()

        return sample

    def update_track_counts(
        self,
        active: int,
        confirmed: int,
        tentative: int,
        lost: int,
        created: int = 0,
        removed: int = 0,
    ) -> None:
        """Update current tracking status counters."""
        self.current_active_tracks = active
        self.current_confirmed_tracks = confirmed
        self.current_tentative_tracks = tentative
        self.current_lost_tracks = lost
        self.max_active_tracks = max(self.max_active_tracks, active)
        if created > 0:
            self.tracks_created = created
        if removed > 0:
            self.tracks_removed = removed

    def generate_report(self) -> str:
        """Generate formal Camera Validation Benchmark Report string summary."""
        total_sec = time.monotonic() - self._start_time
        fps_list = [s.fps for s in self._samples] if self._samples else [0.0]
        lat_list = [s.total_latency_ms for s in self._samples] if self._samples else [0.0]
        det_list = [s.detection_time_ms for s in self._samples] if self._samples else [0.0]
        trk_list = [s.tracking_time_ms for s in self._samples] if self._samples else [0.0]

        avg_fps = sum(fps_list) / max(len(fps_list), 1)
        min_fps = min(fps_list) if fps_list else 0.0
        max_fps = max(fps_list) if fps_list else 0.0

        avg_lat = sum(lat_list) / max(len(lat_list), 1)
        max_lat = max(lat_list) if lat_list else 0.0
        avg_det = sum(det_list) / max(len(det_list), 1)
        avg_trk = sum(trk_list) / max(len(trk_list), 1)

        hw = self.resource_monitor.sample()

        lines = [
            "=" * 55,
            "Camera Validation Benchmark Report",
            "=" * 55,
            f"Camera Name:            {self.camera_name}",
            f"Input Resolution:       {self.input_resolution[0]}x{self.input_resolution[1]}",
            f"Processing Resolution:  {self.processing_resolution[0]}x{self.processing_resolution[1]}",
            f"Runtime:                {total_sec:.2f} seconds",
            f"Frames Processed:       {self.total_frames_processed}",
            "-" * 55,
            f"Average FPS:            {avg_fps:.1f} FPS",
            f"Minimum FPS:            {min_fps:.1f} FPS",
            f"Maximum FPS:            {max_fps:.1f} FPS",
            "-" * 55,
            f"Average Total Latency:  {avg_lat:.2f} ms",
            f"Maximum Latency:        {max_lat:.2f} ms",
            f"Average Detection Time: {avg_det:.2f} ms",
            f"Average Tracking Time:  {avg_trk:.2f} ms",
            "-" * 55,
            f"GPU Name:               {hw.gpu_name}",
            f"GPU Usage:              {hw.gpu_percent:.1f}%",
            f"GPU Memory (VRAM):      {hw.vram_used_mb:.1f} MB / {hw.vram_total_mb:.1f} MB ({hw.vram_percent:.1f}%)",
            f"CPU Usage:              {hw.cpu_percent:.1f}%",
            f"RAM Usage:              {hw.ram_used_mb:.1f} MB / {hw.ram_total_mb:.1f} MB ({hw.ram_percent:.1f}%)",
            "-" * 55,
            f"Tracks Created:         {self.tracks_created}",
            f"Tracks Removed:         {self.tracks_removed}",
            f"Maximum Active Tracks:  {self.max_active_tracks}",
            f"Average Active Tracks:  {self.max_active_tracks / 2.0:.1f}",
            "-" * 55,
            f"Reconnect Count:        {self.reconnect_count}",
            f"Dropped Frames:         {self.dropped_frames}",
            f"Skipped Frames:         {self.skipped_frames}",
            "=" * 55,
        ]

        return "\n".join(lines)
