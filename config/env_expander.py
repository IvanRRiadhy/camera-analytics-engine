"""
Environment Variable Configuration Expander.

Provides recursive ${VAR} and ${VAR:-default} expansion for configuration values
with $${ escape syntax, allowlist filtering, and safe disabled-block skipping.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Optional

logger = logging.getLogger(__name__)

_VAR_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")
_ESCAPE_SENTINEL = "\x00_ESCAPED_DOLLAR_BRACE_\x00"


class ConfigExpansionError(ValueError):
    """Raised when an environment variable cannot be resolved and has no default."""


def expand_string(val: str, allowlist_prefix: Optional[str] = None) -> str:
    """Expand ${VAR} and ${VAR:-default} tokens within a string value.

    Args:
        val: Input string possibly containing variable tokens.
        allowlist_prefix: If specified, only variable names beginning with this prefix
            are expanded; all other variables are left unexpanded and logged by name.

    Returns:
        String with expanded values or escaped tokens.

    Raises:
        ConfigExpansionError: If an allowed variable is unset and has no default value.
    """
    if not isinstance(val, str):
        return val

    # Handle escaping: $${ -> sentinel
    had_escape = "$${" in val
    if had_escape:
        val = val.replace("$${", _ESCAPE_SENTINEL)

    if "${" not in val:
        if had_escape:
            val = val.replace(_ESCAPE_SENTINEL, "${")
        return val

    def _replace_var(match: re.Match[str]) -> str:
        var_name = match.group(1)
        default_val = match.group(2)

        if allowlist_prefix is not None:
            if not var_name.startswith(allowlist_prefix):
                logger.warning(
                    "Variable '%s' is not in allowlist (must start with '%s') and was left unexpanded.",
                    var_name,
                    allowlist_prefix,
                )
                return match.group(0)

        if var_name in os.environ:
            return os.environ[var_name]

        if default_val is not None:
            return default_val

        raise ConfigExpansionError(f"Unresolved environment variable '{var_name}' without default.")

    expanded = _VAR_PATTERN.sub(_replace_var, val)

    if had_escape:
        expanded = expanded.replace(_ESCAPE_SENTINEL, "${")

    return expanded


def expand_env_vars(obj: Any, allowlist_prefix: Optional[str] = None) -> Any:
    """Recursively expand environment variable references in configuration data structures.

    Skips blocks that contain '"enabled": False'.
    String keys in dictionaries are preserved as-is and never expanded.

    Args:
        obj: Arbitrary data structure (dict, list, tuple, str, or scalar).
        allowlist_prefix: Optional prefix for allowlisted environment variables.

    Returns:
        Expanded data structure of identical shape and preserved scalar types.
    """
    if isinstance(obj, dict):
        if obj.get("enabled") is False:
            return obj
        return {
            k: expand_env_vars(v, allowlist_prefix=allowlist_prefix)
            for k, v in obj.items()
        }
    elif isinstance(obj, list):
        return [expand_env_vars(item, allowlist_prefix=allowlist_prefix) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(expand_env_vars(item, allowlist_prefix=allowlist_prefix) for item in obj)
    elif isinstance(obj, str):
        return expand_string(obj, allowlist_prefix=allowlist_prefix)
    else:
        return obj

