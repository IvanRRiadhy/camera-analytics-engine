"""
Centralized Runtime Resource Manager for CCTV Analytics AI Engine.

Provides unified, environment-aware path resolution for all engine assets:
- Python Source Execution (`Path.cwd()`)
- Frozen Executable (`sys.frozen = True`, PyInstaller `sys._MEIPASS`)
- Executable Directory (`Path(sys.executable).parent`)
- Working Directory (`Path.cwd()`)

Guarantees 100% path resolution parity between IDE source execution and packaged binaries.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class RuntimeResourceManager:
    """Centralized resource path resolver for CCTV Analytics AI Engine."""

    _instance: Optional[RuntimeResourceManager] = None

    def __init__(self) -> None:
        self._is_frozen: bool = getattr(sys, "frozen", False)
        self._meipass: Optional[Path] = Path(sys._MEIPASS) if hasattr(sys, "_MEIPASS") else None
        self._exec_dir: Path = Path(sys.executable).parent if self._is_frozen else Path.cwd()
        self._cwd: Path = Path.cwd()

    @classmethod
    def get_instance(cls) -> RuntimeResourceManager:
        """Return singleton instance of RuntimeResourceManager."""
        if cls._instance is None:
            cls._instance = RuntimeResourceManager()
        return cls._instance

    @property
    def is_frozen(self) -> bool:
        """Return True if running inside a frozen executable (e.g. PyInstaller)."""
        return self._is_frozen

    @property
    def executable_dir(self) -> Path:
        """Return directory containing the executable binary (or CWD in Python mode)."""
        return self._exec_dir

    @property
    def meipass_dir(self) -> Optional[Path]:
        """Return PyInstaller temp extraction directory (sys._MEIPASS) if frozen."""
        return self._meipass

    def resolve(self, relative_path: str | Path) -> Path:
        """Resolve a relative resource path to an absolute path.

        Search Priority:
        1. If frozen and path exists in `sys._MEIPASS`, return `_MEIPASS / path`.
        2. If path exists relative to executable directory, return `exec_dir / path`.
        3. If path exists relative to CWD, return `cwd / path`.
        4. Fallback to `exec_dir / path` (creating parent if needed).
        """
        rel_path = Path(relative_path)
        if rel_path.is_absolute():
            return rel_path

        # 1. Check sys._MEIPASS for bundled internal resources
        if self._is_frozen and self._meipass is not None:
            meipass_target = self._meipass / rel_path
            if meipass_target.exists():
                return meipass_target

        # 2. Check relative to executable directory
        exec_target = self._exec_dir / rel_path
        if exec_target.exists():
            return exec_target

        # 3. Check relative to current working directory
        cwd_target = self._cwd / rel_path
        if cwd_target.exists():
            return cwd_target

        # 4. Default fallback to executable directory
        return exec_target

    def resolve_writable_dir(self, relative_path: str | Path) -> Path:
        """Resolve and ensure existence of a writable directory.

        Writable directories (logs, cache, runtime, output, recordings, exports) are
        always anchored to the user's working directory or executable directory.
        """
        target_dir = self.resolve(relative_path)
        target_dir.mkdir(parents=True, exist_ok=True)
        return target_dir

    def resolve_model_path(self, model_filename: str) -> Path:
        """Resolve model weights file path (checks models/, MiVOLO weights folder, and CWD)."""
        rel = Path(model_filename)
        if rel.is_absolute() and rel.exists():
            return rel

        # 1. Check direct filename / path
        direct = self.resolve(rel)
        if direct.exists():
            return direct

        # 2. Check models/ subfolder
        in_models = self.resolve(Path("models") / rel.name)
        if in_models.exists():
            return in_models

        # 3. Check subfolders (e.g. camera_analytics/models/human/mivolo/weights)
        mivolo_dir = self.resolve(Path("camera_analytics/models/human/mivolo/weights") / rel.name)
        if mivolo_dir.exists():
            return mivolo_dir

        return in_models

    def resolve_config_path(self, config_filename: str = "configs/standalone.json") -> Path:
        """Resolve standalone configuration JSON file path.
        
        Always prioritizes external user-editable configs (in exec_dir/configs or cwd/configs)
        before falling back to internal bundled copies.
        """
        rel = Path(config_filename)
        if rel.is_absolute() and rel.exists():
            return rel

        # 1. Check relative to current working directory
        cwd_target = self._cwd / rel
        if cwd_target.exists():
            return cwd_target
        if (self._cwd / "configs" / rel.name).exists():
            return self._cwd / "configs" / rel.name

        # 2. Check relative to executable directory (external to _internal)
        exec_target = self._exec_dir / rel
        if exec_target.exists():
            return exec_target
        if (self._exec_dir / "configs" / rel.name).exists():
            return self._exec_dir / "configs" / rel.name

        # 3. Fallback to default resolve (which checks _MEIPASS)
        return self.resolve(rel)




