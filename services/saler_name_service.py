"""Standardize trading-partner (saler) names using config/settings.py SALER_NAME_MAP."""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

import pandas as pd

from config.settings import SALER_NAME_MAP

_SALER_COLUMN = "saler"


def normalize_saler_key(value) -> str:
    """
    Aggressive match key for saler names:
    lowercase, strip punctuation, collapse spaces.
    """
    text = unicodedata.normalize("NFC", str(value).strip().lower())
    text = text.replace("\xa0", " ")
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


@lru_cache(maxsize=1)
def build_saler_name_lookup() -> dict[str, str]:
    """normalized_key → canonical saler label from SALER_NAME_MAP."""
    lookup: dict[str, str] = {}
    for canonical, aliases in SALER_NAME_MAP.items():
        canonical_label = str(canonical).strip()
        if not canonical_label:
            continue
        keys = [normalize_saler_key(canonical_label)]
        keys.extend(normalize_saler_key(alias) for alias in aliases if str(alias).strip())
        for key in keys:
            if key:
                lookup[key] = canonical_label
    return lookup


def canonicalize_saler_name(value) -> str:
    """Return canonical saler label when mapped; otherwise trimmed original."""
    text = str(value).strip()
    if not text or text.lower() in ("nan", "none"):
        return text
    key = normalize_saler_key(text)
    if not key:
        return text
    return build_saler_name_lookup().get(key, text)


def apply_saler_name_standardization(df: pd.DataFrame) -> pd.DataFrame:
    """Replace column `saler` with canonical names from SALER_NAME_MAP."""
    if df.empty or _SALER_COLUMN not in df.columns:
        return df

    out = df.copy()
    lookup = build_saler_name_lookup()
    if not lookup:
        return out

    def _map_value(raw) -> str:
        text = str(raw).strip()
        if not text or text.lower() in ("nan", "none"):
            return text
        key = normalize_saler_key(text)
        return lookup.get(key, text) if key else text

    out[_SALER_COLUMN] = out[_SALER_COLUMN].map(_map_value)
    return out
