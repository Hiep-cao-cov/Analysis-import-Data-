"""Unknown / rare brand label helpers for storage cleanup."""
from __future__ import annotations

from config.settings import LEGACY_UNKNOWN_BRAND_LABELS


def is_unknown_brand(value) -> bool:
    """True when brand is UNKNOW or legacy bucket labels (e.g. OTHER_CHEMICAL)."""
    key = str(value).strip().upper()
    return key in {label.upper() for label in LEGACY_UNKNOWN_BRAND_LABELS}


def is_empty_label_value(value) -> bool:
    """True when a target column (e.g. TYPE) is missing or blank."""
    if value is None:
        return True
    text = str(value).strip()
    return not text or text.lower() in ("nan", "none", "null")


def should_mark_unknown_brand_row(brand, type_value) -> bool:
    """Mark row for deletion only when BRAND is UNKNOW and TYPE is empty."""
    return is_unknown_brand(brand) and is_empty_label_value(type_value)
