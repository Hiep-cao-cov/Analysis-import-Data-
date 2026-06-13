"""Unknown / rare brand label helpers (training + predict)."""
from __future__ import annotations

from config.settings import COL_TYPE, LEGACY_UNKNOWN_BRAND_LABELS, UNKNOWN_BRAND_LABEL


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


def unknown_brand_delete_reason() -> str:
    return (
        f"unknown_brand: BRAND NAME is {UNKNOWN_BRAND_LABEL} and {COL_TYPE} is empty "
        "(row kept in full export; omit when downloading without marked rows)"
    )


def normalize_predicted_brand(value) -> str:
    """Map legacy model outputs (OTHER_CHEMICAL) to UNKNOW for export."""
    key = str(value).strip().upper()
    if key in {label.upper() for label in LEGACY_UNKNOWN_BRAND_LABELS}:
        return UNKNOWN_BRAND_LABEL
    return str(value).strip() if value is not None and str(value).strip().lower() not in ("nan", "none") else ""