"""
Validation Report Generator.

Exports evaluation metrics and comparison reports in JSON, CSV, and Markdown formats.
"""

from __future__ import annotations

import csv
import json
import logging
from io import StringIO
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ValidationReportGenerator:
    """Formatter and exporter for validation evaluation reports."""

    def __init__(self, metrics: dict[str, Any], dataset_info: Optional[dict[str, Any]] = None) -> None:
        self.metrics = metrics
        self.dataset_info = dataset_info or {}

    def to_json(self) -> str:
        """Format metrics as formatted JSON string."""
        payload = {
            "dataset_info": self.dataset_info,
            "evaluation_metrics": self.metrics,
        }
        return json.dumps(payload, indent=2, ensure_ascii=False)

    def to_csv(self) -> str:
        """Format metrics as structured CSV string."""
        output = StringIO()
        writer = csv.writer(output)

        writer.writerow(["Category", "Metric", "Value"])

        overall = self.metrics.get("overall", {})
        for k, v in overall.items():
            writer.writerow(["Overall", k, v])

        resources = self.metrics.get("resources", {})
        for k, v in resources.items():
            writer.writerow(["Resources", k, v])

        by_type = self.metrics.get("by_event_type", {})
        for evt_type, type_m in by_type.items():
            for k, v in type_m.items():
                writer.writerow([f"Module:{evt_type}", k, v])

        return output.getvalue()

    def to_markdown(self) -> str:
        """Format metrics as GitHub-style Markdown report."""
        ds_id = self.dataset_info.get("dataset_id", "Unknown Dataset")
        scenario = self.dataset_info.get("scenario", "Default")
        tags = self.dataset_info.get("tags", [])

        overall = self.metrics.get("overall", {})
        resources = self.metrics.get("resources", {})
        by_type = self.metrics.get("by_event_type", {})

        md = []
        md.append(f"# Enterprise Analytics Validation Report — `{ds_id}`")
        md.append(f"**Scenario**: {scenario} | **Tags**: `{', '.join(tags)}`\n")

        md.append("## Overall Performance Summary")
        md.append("| Metric | Score / Value |")
        md.append("|---|---|")
        md.append(f"| **Precision** | `{overall.get('precision', 0.0):.4f}` |")
        md.append(f"| **Recall** | `{overall.get('recall', 0.0):.4f}` |")
        md.append(f"| **F1 Score** | `{overall.get('f1_score', 0.0):.4f}` |")
        md.append(f"| **Accuracy** | `{overall.get('accuracy', 0.0):.4f}` |")
        md.append(f"| **True Positives (TP)** | `{overall.get('true_positives', 0)}` |")
        md.append(f"| **False Positives (FP)** | `{overall.get('false_positives', 0)}` |")
        md.append(f"| **False Negatives (FN)** | `{overall.get('false_negatives', 0)}` |")
        md.append(f"| **Avg Detection Delay** | `{overall.get('avg_detection_delay_ms', 0.0):.2f} ms` |\n")

        md.append("## System Resource & Throughput Metrics")
        md.append("| Resource Metric | Measured Value |")
        md.append("|---|---|")
        md.append(f"| **Throughput Speed** | `{resources.get('throughput_fps', 0.0):.1f} FPS` |")
        md.append(f"| **Avg Frame Latency** | `{resources.get('avg_latency_ms', 0.0):.2f} ms` |")
        md.append(f"| **CPU Utilization** | `{resources.get('cpu_utilization_pct', 0.0):.1f}%` |")
        md.append(f"| **Memory Footprint** | `{resources.get('memory_mb', 0.0):.1f} MB` |")
        md.append(f"| **GPU Utilization** | `{resources.get('gpu_utilization_pct', 0.0):.1f}%` |\n")

        md.append("## Event Type Accuracy Breakdown")
        md.append("| Event Type | TP | FP | FN | Precision | Recall | F1 Score |")
        md.append("|---|---|---|---|---|---|---|")
        for evt_type, m in by_type.items():
            md.append(
                f"| `{evt_type}` | {m.get('true_positives', 0)} | {m.get('false_positives', 0)} | {m.get('false_negatives', 0)} | "
                f"`{m.get('precision', 0.0):.4f}` | `{m.get('recall', 0.0):.4f}` | `{m.get('f1_score', 0.0):.4f}` |"
            )

        return "\n".join(md)

    def export(self, output_dir: str | Path, base_filename: str = "validation_report") -> dict[str, Path]:
        """Export report in JSON, CSV, and Markdown formats to disk.

        Args:
            output_dir: Target output directory path.
            base_filename: Base filename prefix.

        Returns:
            Dictionary mapping format name to written file Path.
        """
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        json_path = out_path / f"{base_filename}.json"
        csv_path = out_path / f"{base_filename}.csv"
        md_path = out_path / f"{base_filename}.md"

        json_path.write_text(self.to_json(), encoding="utf-8")
        csv_path.write_text(self.to_csv(), encoding="utf-8")
        md_path.write_text(self.to_markdown(), encoding="utf-8")

        logger.info("ValidationReportGenerator exported reports to %s (.json, .csv, .md)", out_path)
        return {"json": json_path, "csv": csv_path, "markdown": md_path}
