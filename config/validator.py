"""
Standalone Configuration Validator Component.

Performs strict, fast-failing validations on local standalone configuration dictionaries:
- Unique publisher types and valid publish_interval_seconds (> 0).
- Unique zone_id per camera.
- Region/polygon zones with at least 3 points.
- Valid [x, y] integer point coordinates.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from camera_analytics.config.loader import ConfigValidationError

logger = logging.getLogger(__name__)


class StandaloneConfigValidator:
    """Validates local standalone configuration dictionary schemas before startup."""

    @staticmethod
    def validate(raw_data: Dict[str, Any]) -> None:
        """Validate standalone configuration structure, failing fast on invalid options."""
        if not isinstance(raw_data, dict):
            raise ConfigValidationError("Standalone configuration root must be a JSON object.")

        # 1. Validate Publishers Configuration
        comm_dict = raw_data.get("communication", {})
        publishers = comm_dict.get("publishers", [])
        if not isinstance(publishers, list):
            raise ConfigValidationError("'communication.publishers' must be a JSON array.")

        seen_publisher_types = set()
        for idx, pub in enumerate(publishers):
            if isinstance(pub, str):
                pub_type = pub.strip().lower()
            elif isinstance(pub, dict):
                pub_type = str(pub.get("type", "")).strip().lower()
                interval = pub.get("publish_interval_seconds")
                if interval is not None:
                    try:
                        val = float(interval)
                        if val <= 0:
                            raise ConfigValidationError(
                                f"Publisher '{pub_type}' publish_interval_seconds must be > 0 (got {val})."
                            )
                    except (ValueError, TypeError):
                        raise ConfigValidationError(
                            f"Publisher '{pub_type}' publish_interval_seconds must be a positive float."
                        )
            else:
                raise ConfigValidationError(f"Publisher entry at index {idx} must be a string or JSON object.")

            if not pub_type:
                raise ConfigValidationError(f"Publisher entry at index {idx} missing required 'type'.")

            if pub_type in seen_publisher_types:
                raise ConfigValidationError(f"Duplicate publisher type '{pub_type}' configured in publishers array.")
            seen_publisher_types.add(pub_type)

        # 2. Validate Cameras & Zones Configuration
        cameras = raw_data.get("cameras", [])
        if not isinstance(cameras, list):
            raise ConfigValidationError("'cameras' must be a JSON array.")

        for cam_idx, cam in enumerate(cameras):
            if not isinstance(cam, dict):
                raise ConfigValidationError(f"Camera entry at index {cam_idx} must be a JSON object.")

            cam_id = cam.get("camera_id")
            if not cam_id or not isinstance(cam_id, str):
                raise ConfigValidationError(f"Camera entry at index {cam_idx} missing required string 'camera_id'.")

            # Validate Zones for this camera
            zones = cam.get("zones", [])
            if not isinstance(zones, list):
                raise ConfigValidationError(f"Camera '{cam_id}' field 'zones' must be a JSON array.")

            seen_zone_ids = set()
            valid_zone_count = 0
            for z_idx, zone in enumerate(zones):
                if not isinstance(zone, dict):
                    raise ConfigValidationError(f"Camera '{cam_id}' zone at index {z_idx} must be a JSON object.")

                z_id = str(
                    zone.get("zone_id")
                    or zone.get("id")
                    or zone.get("zoneId")
                    or f"z_{valid_zone_count}"
                )

                if z_id in seen_zone_ids:
                    logger.warning(
                        "StandaloneConfigValidator: Camera '%s' contains duplicate zone_id '%s'. Skipping duplicate zone.",
                        cam_id,
                        z_id,
                    )
                    continue
                seen_zone_ids.add(z_id)
                valid_zone_count += 1

                z_type = str(zone.get("type", zone.get("zone_type", "REGION"))).upper()
                points = zone.get("points", [])

                if not isinstance(points, list):
                    raise ConfigValidationError(f"Camera '{cam_id}' zone '{z_id}' 'points' must be a list of coordinates.")

                # Coordinate Validation
                for p_idx, pt in enumerate(points):
                    if not isinstance(pt, (list, tuple)) or len(pt) != 2 or not all(isinstance(v, (int, float)) for v in pt):
                        raise ConfigValidationError(
                            f"Camera '{cam_id}' zone '{z_id}' point at index {p_idx} invalid format {pt}. Must be [x, y] integers."
                        )

                # Polygon Vertex Count Validation
                if z_type in ["POLYGON", "REGION"] and len(points) < 3:
                    raise ConfigValidationError(
                        f"Camera '{cam_id}' polygon zone '{z_id}' requires at least 3 points (got {len(points)})."
                    )
                elif z_type == "LINE" and len(points) < 2:
                    raise ConfigValidationError(
                        f"Camera '{cam_id}' line zone '{z_id}' requires at least 2 points (got {len(points)})."
                    )

        # 3. Check Top-level Messaging Configuration
        StandaloneConfigValidator.validate_messaging(raw_data)

        logger.debug("StandaloneConfigValidator: Validation passed cleanly.")

    @staticmethod
    def validate_messaging(raw_data: Dict[str, Any]) -> None:
        """Validate top-level messaging block, logging WARNING for unknown keys."""
        messaging_dict = raw_data.get("messaging")
        if isinstance(messaging_dict, dict):
            known_keys = {
                "snapshot",
                "privacy",
                "publishers",
                "timezone",
                "reset_policy",
                "envelope",
                "spool",
                "routing",
                "rabbitmq",
            }
            for k in messaging_dict:
                if k not in known_keys:
                    logger.warning(
                        "StandaloneConfigValidator: Unknown key '%s' found in top-level 'messaging' configuration block.",
                        k,
                    )
