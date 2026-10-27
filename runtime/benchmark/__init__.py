"""
CCTV Analytics AI Engine Runtime Benchmark Package.
"""

from camera_analytics.runtime.benchmark.benchmark_runner import BenchmarkResult, BenchmarkScenario, RuntimeBenchmarkRunner
from camera_analytics.runtime.benchmark.html_reporter import BenchmarkHtmlReporter
from camera_analytics.runtime.benchmark.parity_validator import RuntimeParityValidator

__all__ = [
    "RuntimeBenchmarkRunner",
    "BenchmarkScenario",
    "BenchmarkResult",
    "RuntimeParityValidator",
    "BenchmarkHtmlReporter",
]
