"""
Identity Resolution Component.

Provides unified resolution for application_id across environment variables,
configuration hierarchies, and mode-dependent fallbacks.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

ZERO_UUID_PLACEHOLDER = "00000000-0000-0000-0000-000000000000"


def resolve_application_id(
    config: Optional[Any] = None,
    mode: str = "standalone",
    application_id: Optional[str] = None,
) -> str:
    """Resolve authoritative application_id across environment, config, and mode fallbacks.

    Precedence:
        1. Explicitly provided application_id argument (if non-empty).
        2. APPLICATION_ID environment variable.
        3. Config key 'application_id' under engine block or top-level.
        4. In standalone mode: Zero-UUID placeholder ('00000000-0000-0000-0000-000000000000') with a WARNING.
        5. In enterprise mode: Startup failure raising RuntimeError.

    Args:
        config: Optional configuration dictionary, EngineConfig, or ConfigurationSnapshot.
        mode: Operational mode ('standalone' or 'enterprise').
        application_id: Explicitly passed override string if available.

    Returns:
        Resolved application UUID string.

    Raises:
        RuntimeError: If enterprise mode lacks application_id.
    """
    if application_id and str(application_id).strip():
        return str(application_id).strip()

    env_app_id = os.getenv("APPLICATION_ID")
    if env_app_id and env_app_id.strip():
        return env_app_id.strip()

    # Inspect configuration dictionary or object
    cfg_app_id: Optional[str] = None
    if isinstance(config, dict):
        engine_dict = config.get("engine")
        if isinstance(engine_dict, dict):
            cfg_app_id = engine_dict.get("application_id")
        if not cfg_app_id:
            cfg_app_id = config.get("application_id")
    elif config is not None:
        cfg_app_id = getattr(config, "application_id", None)
        if not cfg_app_id and hasattr(config, "engine"):
            engine_obj = getattr(config, "engine")
            cfg_app_id = getattr(engine_obj, "application_id", None)

    if cfg_app_id and str(cfg_app_id).strip():
        return str(cfg_app_id).strip()

    # Determine mode from config if not explicitly set to enterprise
    resolved_mode = mode
    if resolved_mode != "enterprise" and config is not None:
        if isinstance(config, dict):
            resolved_mode = config.get("engine", {}).get("mode", resolved_mode)
        else:
            engine_obj = getattr(config, "engine", config)
            resolved_mode = getattr(engine_obj, "mode", resolved_mode)

    if resolved_mode == "enterprise":
        raise RuntimeError(
            "Missing required application_id in enterprise mode. "
            "Set APPLICATION_ID environment variable or specify 'application_id' in engine configuration."
        )

    logger.warning(
        "No application_id configured in env or config; "
        "falling back to zero-UUID placeholder '%s' in standalone mode.",
        ZERO_UUID_PLACEHOLDER,
    )
    return ZERO_UUID_PLACEHOLDER

