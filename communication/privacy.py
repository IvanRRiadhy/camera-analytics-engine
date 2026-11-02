"""
Privacy Filter & Data Protection Component.

Applies regulatory privacy masking, field redaction, value-based scrubbing,
and HMAC-SHA256 anonymization to vision events across identities and license plate data.
"""

from __future__ import annotations

import copy
import hashlib
import hmac
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

try:
    from communication.envelope import map_category
except ImportError:
    try:
        from .envelope import map_category
    except ImportError:
        from camera_analytics.communication.envelope import map_category

logger = logging.getLogger(__name__)

# Unambiguous identity keys stripped everywhere across all events outside 'full' mode
UNAMBIGUOUS_NAME_KEYS = {
    "full_name",
    "first_name",
    "last_name",
    "display_name",
    "person_name",
    "department",
    "email",
    "job_title",
}

# Ambiguous keys stripped only inside biometric events (e.g. FACE_IDENTIFIED, PERSON_*)
AMBIGUOUS_NAME_KEYS = {
    "name",
    "title",
    "position",
}

# Complete set of sensitive name-like and job/title keys
NAME_LIKE_FIELDS = UNAMBIGUOUS_NAME_KEYS | AMBIGUOUS_NAME_KEYS


@dataclass(frozen=True)
class PrivacyConfig:
    """Configuration container for identity and license plate privacy filtering."""

    identity_mode: str = "full"  # "full" | "id_only" | "hashed"
    plate_mode: str = "full"     # "full" | "masked" | "hashed"
    hmac_salt: Optional[str] = field(default=None, repr=False)

    def __repr__(self) -> str:
        return f"PrivacyConfig(identity_mode='{self.identity_mode}', plate_mode='{self.plate_mode}')"

    def __str__(self) -> str:
        return self.__repr__()

    def __post_init__(self) -> None:
        """Validate modes and salt requirements at initialization time (fail fast)."""
        valid_identity_modes = {"full", "id_only", "hashed"}
        valid_plate_modes = {"full", "masked", "hashed"}

        id_m = str(self.identity_mode).lower().strip()
        pl_m = str(self.plate_mode).lower().strip()

        if id_m not in valid_identity_modes:
            raise ValueError(f"Unknown identity_mode '{self.identity_mode}'. Allowed: {sorted(valid_identity_modes)}")
        if pl_m not in valid_plate_modes:
            raise ValueError(f"Unknown plate_mode '{self.plate_mode}'. Allowed: {sorted(valid_plate_modes)}")

        object.__setattr__(self, "identity_mode", id_m)
        object.__setattr__(self, "plate_mode", pl_m)

        # Fail fast if hashed mode is selected without salt
        if id_m == "hashed" or pl_m == "hashed":
            resolved_salt = self.hmac_salt or os.getenv("HMAC_SALT")
            if not resolved_salt or not str(resolved_salt).strip():
                raise ValueError("Missing or empty HMAC salt required for hashed privacy mode")
            object.__setattr__(self, "hmac_salt", str(resolved_salt).strip())

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]] = None, mode: str = "standalone") -> PrivacyConfig:
        """Build explicit PrivacyConfig using safe defaults per deployment mode.

        Defaults:
            - enterprise: identity_mode="id_only", plate_mode="masked"
            - standalone: identity_mode="full", plate_mode="full"
        """
        raw = data or {}
        is_enterprise = str(mode).lower() == "enterprise"

        default_id = "id_only" if is_enterprise else "full"
        default_pl = "masked" if is_enterprise else "full"

        identity_mode = raw.get("identity_mode", default_id)
        plate_mode = raw.get("plate_mode", default_pl)
        hmac_salt = raw.get("hmac_salt", os.getenv("HMAC_SALT"))

        return cls(
            identity_mode=identity_mode,
            plate_mode=plate_mode,
            hmac_salt=hmac_salt,
        )


def normalize_plate_for_hash(plate: str) -> str:
    """Normalize plate before HMAC: uppercase with all whitespace and hyphens removed."""
    return re.sub(r"[\s\-]+", "", str(plate).upper())


def normalize_person_id_for_hash(person_id: str) -> str:
    """Normalize person_id before HMAC: unchanged except strip()."""
    return str(person_id).strip()


def _recursive_strip_name_keys(obj: Any, strip_keys_lower: set[str]) -> Any:
    """Recursively strip name-like keys across all dictionaries and lists (case-insensitive)."""
    if isinstance(obj, dict):
        return {
            k: _recursive_strip_name_keys(v, strip_keys_lower)
            for k, v in obj.items()
            if str(k).lower() not in strip_keys_lower
        }
    elif isinstance(obj, list):
        return [_recursive_strip_name_keys(item, strip_keys_lower) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(_recursive_strip_name_keys(item, strip_keys_lower) for item in obj)
    return obj


def _recursive_value_scrub(
    obj: Any,
    plate_norm: Optional[str] = None,
    name_norm: Optional[str] = None,
    replacement: str = "[redacted]",
    path: str = "",
) -> Any:
    """Replace any string value anywhere containing the event's own plate or person name with [redacted].

    Plate exemption is path-based: only exact paths attributes.plate_text and attributes.plate (and subkeys)
    are exempt from plate value scrub.
    """
    is_plate_exempt = (
        path in ("attributes.plate_text", "attributes.plate", "plate_text", "plate")
        or path.startswith("attributes.plate.")
        or path.startswith("plate.")
    )

    if isinstance(obj, str):
        if obj == replacement:
            return obj
        # Scrub plate match (if not exempt path, non-empty, and len >= 3)
        if not is_plate_exempt and plate_norm and len(plate_norm) >= 3:
            compact_s = re.sub(r"[\s\-]+", "", obj).upper()
            if plate_norm in compact_s:
                return replacement
        # Scrub person name match (whole token, non-alphanumeric boundaries, len >= 3)
        if name_norm and len(name_norm) >= 3:
            pattern = r"(?<![A-Za-z0-9])" + re.escape(name_norm) + r"(?![A-Za-z0-9])"
            if re.search(pattern, obj, re.IGNORECASE):
                return replacement
        return obj
    elif isinstance(obj, dict):
        if is_plate_exempt and not name_norm:
            return obj
        res = {}
        for k, v in obj.items():
            child_path = f"{path}.{k}" if path else str(k)
            if (
                (child_path in ("attributes.plate_text", "attributes.plate", "plate_text", "plate")
                 or child_path.startswith("attributes.plate.")
                 or child_path.startswith("plate."))
                and not name_norm
            ):
                res[k] = v
            else:
                res[k] = _recursive_value_scrub(
                    v,
                    plate_norm=plate_norm,
                    name_norm=name_norm,
                    replacement=replacement,
                    path=child_path,
                )
        return res
    elif isinstance(obj, list):
        return [
            _recursive_value_scrub(
                item,
                plate_norm=plate_norm,
                name_norm=name_norm,
                replacement=replacement,
                path=f"{path}[{idx}]",
            )
            for idx, item in enumerate(obj)
        ]
    elif isinstance(obj, tuple):
        return tuple(
            _recursive_value_scrub(
                item,
                plate_norm=plate_norm,
                name_norm=name_norm,
                replacement=replacement,
                path=f"{path}[{idx}]",
            )
            for idx, item in enumerate(obj)
        )
    return obj


class PrivacyFilter:
    """Filter that sanitizes identity attributes and license plate details."""

    def __init__(self, config: Optional[PrivacyConfig] = None) -> None:
        self.config = config or PrivacyConfig()

    def _hash_plate(self, plate: str) -> str:
        """Compute HMAC-SHA256 digest of normalized plate using configured salt."""
        salt = self.config.hmac_salt or ""
        norm = normalize_plate_for_hash(plate)
        return hmac.new(salt.encode("utf-8"), norm.encode("utf-8"), hashlib.sha256).hexdigest()

    def _hash_person_id(self, person_id: str) -> str:
        """Compute HMAC-SHA256 digest of normalized person_id using configured salt."""
        salt = self.config.hmac_salt or ""
        norm = normalize_person_id_for_hash(person_id)
        return hmac.new(salt.encode("utf-8"), norm.encode("utf-8"), hashlib.sha256).hexdigest()

    def _hash_value(self, value: str) -> str:
        """Backward-compatible HMAC-SHA256 digest calculation."""
        salt = self.config.hmac_salt or ""
        return hmac.new(salt.encode("utf-8"), str(value).encode("utf-8"), hashlib.sha256).hexdigest()

    @staticmethod
    def _parse_tnkb(raw_plate: Optional[str]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Deterministic in-repo TNKB decomposition for Indonesian license plates."""
        if raw_plate is None:
            return None, None, None
        raw_str = str(raw_plate).strip().upper()
        compact = re.sub(r"[\s\.\-]+", "", raw_str)
        if not compact:
            return None, None, None

        digit_matches = list(re.finditer(r"\d+", compact))
        if not digit_matches:
            return compact, None, None

        dm = digit_matches[0]
        pfx = compact[:dm.start()] if dm.start() > 0 else None
        num = dm.group()
        sfx = compact[dm.end():] if dm.end() < len(compact) else None
        return pfx, num, sfx

    def _format_and_filter_plate(
        self,
        raw_plate_text: str,
        status: str,
    ) -> Tuple[str, Dict[str, Any], Optional[str]]:
        """Decompose plate, determine validation, and apply plate_mode filtering."""
        pfx, num, sfx = self._parse_tnkb(raw_plate_text)
        is_grammar_valid = (status == "GRAMMAR_VALID")

        parsed = is_grammar_valid and (pfx is not None and len(pfx) <= 2)

        # Base plate dict
        plate_dict: Dict[str, Any] = {
            "prefix": pfx if (pfx and len(pfx) <= 2) else None,
            "number": num,
            "suffix": sfx,
            "parsed": parsed,
            "status": status,
        }

        # Text formulation
        if parsed and pfx and num:
            spaced_text = f"{pfx} {num} {sfx}".strip() if sfx else f"{pfx} {num}"
        else:
            # Fall back to raw unspaced string
            spaced_text = raw_plate_text

        mode = self.config.plate_mode

        if mode == "full":
            plate_dict["raw_text"] = raw_plate_text
            return spaced_text, plate_dict, raw_plate_text

        elif mode == "masked":
            # Mask number with asterisks, keep suffix partially (1st char kept, rest *)
            if parsed and pfx and num:
                masked_num = len(num) * "*"
                masked_sfx = sfx[0] + ("*" * (len(sfx) - 1)) if sfx else None

                plate_dict["number"] = masked_num
                plate_dict["suffix"] = masked_sfx

                masked_text = f"{pfx} {masked_num} {masked_sfx}".strip() if masked_sfx else f"{pfx} {masked_num}"
            else:
                # Unparsed / arbitrary plate text masking
                plate_dict["prefix"] = None
                plate_dict["number"] = None
                plate_dict["suffix"] = None
                if len(raw_plate_text) > 3:
                    masked_text = raw_plate_text[:1] + ("*" * (len(raw_plate_text) - 2)) + raw_plate_text[-1:]
                else:
                    masked_text = len(raw_plate_text) * "*"

            plate_dict.pop("raw_text", None)
            return masked_text, plate_dict, None

        elif mode == "hashed":
            hashed_plate = self._hash_plate(raw_plate_text)
            plate_dict["prefix"] = None
            plate_dict["number"] = None
            plate_dict["suffix"] = None
            plate_dict["hash"] = hashed_plate
            plate_dict.pop("raw_text", None)
            return hashed_plate, plate_dict, None

        return spaced_text, plate_dict, None

    def filter_event(self, event_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Apply privacy filtering rules, key stripping, and value scrub to event dictionary.

        Args:
            event_dict: Event payload dictionary.

        Returns:
            Sanitized event dictionary.
        """
        filtered = copy.deepcopy(event_dict)
        attrs = filtered.get("attributes")
        if not isinstance(attrs, dict):
            attrs = {}
            filtered["attributes"] = attrs

        evt_type = str(filtered.get("event_type", attrs.get("event_type", ""))).upper()

        raw_plate_for_scrub: Optional[str] = None
        raw_name_for_scrub: Optional[str] = None

        # 1. License Plate Processing (VEHICLE_LPR)
        if "LPR" in evt_type or "VEHICLE" in evt_type or "plate_text" in attrs:
            raw_text = str(attrs.get("plate_text", "")).strip()
            status = str(attrs.get("status", "REVIEW"))
            if raw_text:
                raw_plate_for_scrub = raw_text

            disp_text, plate_dict, raw_kept = self._format_and_filter_plate(raw_text, status)
            attrs["plate_text"] = disp_text
            attrs["plate"] = plate_dict

            if raw_kept is not None:
                attrs["raw_text"] = raw_kept
            else:
                attrs.pop("raw_text", None)

        # 2. Identity & Person Processing (FACE_IDENTIFIED or people analytics)
        id_mode = self.config.identity_mode

        # Determine category: prefer pre-computed "category" from envelope, fall back to map_category
        raw_cat = filtered.get("category")
        if raw_cat is not None:
            category = str(raw_cat.value if hasattr(raw_cat, "value") else raw_cat).lower()
        else:
            plugin_name = str(filtered.get("plugin_name", attrs.get("plugin_name", "")))
            category = map_category(evt_type, plugin_name)
        is_biometric = (category == "biometric")

        # Capture raw person name for value scrubbing before stripping
        name_keys = ("full_name", "person_name", "name") if is_biometric else ("full_name", "person_name")
        for name_key in name_keys:
            val = attrs.get(name_key) or filtered.get(name_key)
            if val and isinstance(val, str) and val.strip():
                raw_name_for_scrub = val.strip()
                break

        if id_mode != "full":
            if is_biometric:
                # Inside biometric events, strip unambiguous keys plus ambiguous keys (name, title, position)
                strip_keys = {k.lower() for k in (UNAMBIGUOUS_NAME_KEYS | AMBIGUOUS_NAME_KEYS)}
            else:
                # Outside biometric events, strip only unambiguous identity keys (preserve zone name, bbox position, etc.)
                strip_keys = {k.lower() for k in UNAMBIGUOUS_NAME_KEYS}

            filtered = _recursive_strip_name_keys(filtered, strip_keys)
            attrs = filtered.get("attributes", {})

            # Handle person_id hashing if requested
            if id_mode == "hashed":
                if "person_id" in attrs and attrs["person_id"]:
                    attrs["person_id"] = self._hash_person_id(str(attrs["person_id"]))
                if "person_id" in filtered and filtered["person_id"]:
                    filtered["person_id"] = self._hash_person_id(str(filtered["person_id"]))

        # 3. Defense-in-depth Value Scrub (Task 1 & Task 3)
        # In plate_mode masked/hashed, scrub plate; in id_mode id_only/hashed, scrub person name
        scrub_plate = (self.config.plate_mode in ("masked", "hashed")) and bool(raw_plate_for_scrub)
        scrub_name = (self.config.identity_mode in ("id_only", "hashed")) and bool(raw_name_for_scrub)

        if scrub_plate or scrub_name:
            plate_norm = normalize_plate_for_hash(raw_plate_for_scrub) if scrub_plate else None
            name_norm = raw_name_for_scrub.strip() if scrub_name else None
            filtered = _recursive_value_scrub(
                filtered,
                plate_norm=plate_norm,
                name_norm=name_norm,
                path="",
            )

        return filtered
