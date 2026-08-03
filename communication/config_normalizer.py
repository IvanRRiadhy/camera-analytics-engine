"""
Unified Configuration Normalizer Component.

Serves as the single source of truth for parsing raw configuration inputs (strings or dict objects),
transforming them into clean, standardized dictionary publisher definitions.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class ConfigNormalizer:
    """Centralized configuration normalizer for Communication Layer."""

    @staticmethod
    def normalize_publishers(config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Normalize raw configuration dictionary into standardized list of publisher dicts.
        
        Supports:
        - "communication": {"publishers": ["console", "log"]}
        - "communication": {"publishers": [{"type": "console", "enabled": true}]}
        - "publishers": [...]
        """
        comm_cfg = config.get("communication", {})
        raw_publishers = comm_cfg.get("publishers", config.get("publishers", []))

        normalized: List[Dict[str, Any]] = []

        if not raw_publishers:
            return normalized

        for item in raw_publishers:
            if isinstance(item, str):
                clean_type = item.strip().lower()
                normalized.append({
                    "type": clean_type,
                    "name": clean_type,
                    "enabled": True,
                })
            elif isinstance(item, dict):
                pub_type = item.get("type", "").strip().lower()
                if pub_type:
                    normalized.append({
                        **item,
                        "type": pub_type,
                        "name": item.get("name", pub_type),
                        "enabled": item.get("enabled", True),
                    })

        return normalized
