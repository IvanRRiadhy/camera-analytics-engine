"""
Validation Dataset Manager.

Loads, manages, and filters dataset directories containing manifest.json, ground_truth.json,
camera layout configurations, and video files.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

from camera_analytics.validation.schema import DatasetManifest, GroundTruthEvent

logger = logging.getLogger(__name__)


class ValidationDataset:
    """Represents a single validation dataset instance loaded from disk."""

    def __init__(self, dataset_dir: str | Path) -> None:
        self.path = Path(dataset_dir).resolve()
        self.manifest: DatasetManifest = DatasetManifest(dataset_id=self.path.name)
        self.ground_truth: list[GroundTruthEvent] = []
        self.camera_config: dict[str, Any] = {}
        self._is_loaded = False
        self.load()

    def load(self) -> None:
        """Load manifest, camera configuration, and ground truth annotations from disk."""
        if not self.path.exists():
            raise FileNotFoundError(f"Dataset directory '{self.path}' does not exist.")

        manifest_file = self.path / "manifest.json"
        if manifest_file.exists():
            data = json.loads(manifest_file.read_text(encoding="utf-8"))
            self.manifest = DatasetManifest.from_dict(data)
        else:
            logger.warning("Dataset '%s' missing manifest.json; using default manifest", self.path.name)

        camera_file = self.path / "camera.json"
        if camera_file.exists():
            self.camera_config = json.loads(camera_file.read_text(encoding="utf-8"))

        gt_file = self.path / "ground_truth.json"
        if gt_file.exists():
            gt_data = json.loads(gt_file.read_text(encoding="utf-8"))
            if isinstance(gt_data, list):
                self.ground_truth = [GroundTruthEvent.from_dict(item) for item in gt_data]
            elif isinstance(gt_data, dict) and "events" in gt_data:
                self.ground_truth = [GroundTruthEvent.from_dict(item) for item in gt_data["events"]]

        self._is_loaded = True
        logger.info(
            "ValidationDataset '%s' loaded successfully (%d cameras, %d ground truth events, tags=%s)",
            self.manifest.dataset_id,
            len(self.manifest.cameras),
            len(self.ground_truth),
            self.manifest.tags,
        )

    def has_tag(self, tag: str) -> bool:
        """Check if dataset contains a specific tag."""
        return tag.lower() in [t.lower() for t in self.manifest.tags]


class ValidationDatasetManager:
    """Manager responsible for discovering, indexing, and filtering validation datasets."""

    def __init__(self, root_dir: str | Path = "camera_analytics/datasets") -> None:
        self.root_dir = Path(root_dir)
        self._datasets: dict[str, ValidationDataset] = {}

    def discover_datasets(self) -> list[ValidationDataset]:
        """Scan root directory for dataset directories containing manifest.json or ground_truth.json.

        Returns:
            List of loaded ValidationDataset instances.
        """
        self._datasets.clear()
        if not self.root_dir.exists():
            logger.warning("Dataset root directory '%s' does not exist", self.root_dir)
            return []

        # Find subdirectories containing manifest.json or ground_truth.json
        for path in self.root_dir.iterdir():
            if path.is_dir() and (path / "manifest.json").exists() or (path / "ground_truth.json").exists():
                try:
                    ds = ValidationDataset(path)
                    self._datasets[ds.manifest.dataset_id] = ds
                except Exception as exc:
                    logger.error("Failed to load dataset at '%s': %s", path, exc)

        return list(self._datasets.values())

    def get_dataset(self, dataset_id: str) -> Optional[ValidationDataset]:
        """Get dataset by dataset_id."""
        return self._datasets.get(dataset_id)

    def filter_by_tag(self, tag: str) -> list[ValidationDataset]:
        """Filter discovered datasets by tag (e.g. 'indoor', 'lobby')."""
        return [ds for ds in self._datasets.values() if ds.has_tag(tag)]
