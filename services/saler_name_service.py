"""Standardize trading-partner (saler) names via settings.py regex rules + optional maps."""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

import pandas as pd

from config.settings import (
    SALER_NAME_MAP,
    SALER_NAME_PAREN_REMOVE_KEYWORDS,
    SALER_NAME_REGEX_MAP,
    SALER_NAME_REGEX_REMOVE,
    SALER_NAME_STRIP_CHARACTERS,
)

_SALER_COLUMN = "saler"


def _strip_accents(text: str) -> str:
    """Fold Vietnamese/Unicode accents so Công ty → cong ty."""
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")


def _prepare_saler_text(value) -> str:
    """Lowercase, trim, fold accents — input to regex remove/map steps."""
    text = unicodedata.normalize("NFC", str(value).strip())
    if not text or text.lower() in ("nan", "none"):
        return ""
    text = _strip_accents(text.lower())
    return text.replace("\xa0", " ")


def _collapse_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


@lru_cache(maxsize=1)
def _compiled_paren_remove_patterns() -> tuple[re.Pattern[str], ...]:
    patterns: list[re.Pattern[str]] = []
    for keyword in SALER_NAME_PAREN_REMOVE_KEYWORDS:
        token = str(keyword).strip()
        if not token:
            continue
        patterns.append(
            re.compile(rf"\([^)]*{re.escape(token)}[^)]*\)", re.IGNORECASE)
        )
    return tuple(patterns)


@lru_cache(maxsize=1)
def _compiled_remove_patterns() -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(p, re.IGNORECASE) for p in SALER_NAME_REGEX_REMOVE)


@lru_cache(maxsize=1)
def _compiled_map_rules() -> tuple[tuple[re.Pattern[str], str], ...]:
    rules: list[tuple[re.Pattern[str], str]] = []
    for pattern, canonical in SALER_NAME_REGEX_MAP:
        pat = str(pattern).strip()
        label = str(canonical).strip()
        if pat and label:
            rules.append((re.compile(pat, re.IGNORECASE), label))
    return tuple(rules)


def normalize_saler_key(value) -> str:
    """
    Match key for SALER_NAME_MAP lookup:
    lowercase, remove punctuation, collapse spaces.
    """
    text = _prepare_saler_text(value)
    if not text:
        return ""
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    return _collapse_spaces(text)


def apply_saler_paren_keyword_removals(text: str) -> str:
    """
    Remove entire (... ) segments when inner text contains a configured keyword (e.g. MST).
    Other parentheses such as (VIETNAM) are kept for later cleanup.
    """
    out = text
    for pattern in _compiled_paren_remove_patterns():
        out = pattern.sub(" ", out)
    return _collapse_spaces(out)


def apply_saler_regex_removals(text: str) -> str:
    """Apply SALER_NAME_REGEX_REMOVE to already-lowercased saler text."""
    out = text
    for pattern in _compiled_remove_patterns():
        out = pattern.sub(" ", out)
    return _collapse_spaces(out)


def apply_saler_character_cleanup(text: str) -> str:
    """
    Remove SALER_NAME_STRIP_CHARACTERS (e.g. . ( ) ,) and collapse runs of spaces to one.
    """
    out = text
    for ch in SALER_NAME_STRIP_CHARACTERS:
        out = out.replace(ch, " ")
    return _collapse_spaces(out)


def apply_saler_punctuation_cleanup(text: str) -> str:
    """Replace any remaining punctuation with spaces and collapse to one gap."""
    out = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    return _collapse_spaces(out)


def apply_saler_regex_map(text: str) -> str | None:
    """First matching SALER_NAME_REGEX_MAP rule wins; else None."""
    if not text:
        return None
    for pattern, canonical in _compiled_map_rules():
        if pattern.search(text):
            return canonical
    return None


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


def process_saler_name(value) -> str:
    """
    Process one saler value:
    lowercase → general regex remove → strip punctuation → collapse spaces
    → optional regex/exact map overrides.

    Input: raw `saler` cell value.
    Output: cleaned / canonical saler string for storage and analysis.
    """
    prepared = _prepare_saler_text(value)
    if not prepared:
        return str(value).strip() if value is not None and str(value).strip() else ""

    cleaned = apply_saler_punctuation_cleanup(
        apply_saler_character_cleanup(
            apply_saler_regex_removals(apply_saler_paren_keyword_removals(prepared))
        )
    )

    mapped = apply_saler_regex_map(cleaned)
    if mapped:
        return mapped

    lookup = build_saler_name_lookup()
    if lookup:
        key = normalize_saler_key(cleaned)
        if key and key in lookup:
            return lookup[key]

    return cleaned


def canonicalize_saler_name(value) -> str:
    """Alias for process_saler_name."""
    return process_saler_name(value)


def apply_saler_name_standardization(df: pd.DataFrame) -> pd.DataFrame:
    """Replace column `saler` using process_saler_name on every row."""
    if df.empty or _SALER_COLUMN not in df.columns:
        return df

    out = df.copy()
    out[_SALER_COLUMN] = out[_SALER_COLUMN].map(process_saler_name)
    return out
