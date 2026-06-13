"""Derive Sale_chanel from transport mode (phuong tien van tai)."""
from __future__ import annotations

import re
import unicodedata

import pandas as pd

from config.settings import (
    INDENT_TRANSPORT_LABELS,
    SALE_CHANNEL_COLUMN,
    SALE_CHANNEL_FILTER_OPTIONS,
    SALE_CHANNEL_INDENT_VALUE,
    SALE_CHANNEL_LOCAL_VALUE,
    SALE_CHANNEL_TRANSPORT_COLUMN,
)


def _normalize_transport_label(value) -> str:
    if pd.isna(value):
        return ""
    text = unicodedata.normalize("NFC", str(value).strip())
    text = re.sub(r"\s+", " ", text)
    return text


def _indent_transport_set() -> set[str]:
    return {_normalize_transport_label(label) for label in INDENT_TRANSPORT_LABELS}


def filter_by_sale_channel(df: pd.DataFrame, sale_channel: str) -> pd.DataFrame:
    """Keep rows matching Indent or Local (all volume KPIs/charts use this subset)."""
    if SALE_CHANNEL_COLUMN not in df.columns:
        return df.copy()
    channel = str(sale_channel).strip()
    if channel not in SALE_CHANNEL_FILTER_OPTIONS:
        channel = SALE_CHANNEL_INDENT_VALUE
    return df[df[SALE_CHANNEL_COLUMN].astype(str).str.strip() == channel].copy()


def find_transport_column(df: pd.DataFrame) -> str | None:
    for col in df.columns:
        if str(col).strip().lower() == SALE_CHANNEL_TRANSPORT_COLUMN:
            return col
    return None


def add_sale_channel_column(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add Sale_chanel:
    - Indent if phuong tien van tai matches INDENT_TRANSPORT_LABELS in settings.py
    - Local otherwise (including missing transport)
    """
    out = df.copy()
    transport_col = find_transport_column(out)
    indent_labels = _indent_transport_set()

    if transport_col is None:
        if SALE_CHANNEL_COLUMN not in out.columns:
            out[SALE_CHANNEL_COLUMN] = SALE_CHANNEL_LOCAL_VALUE
        return out

    normalized = out[transport_col].map(_normalize_transport_label)
    out[SALE_CHANNEL_COLUMN] = normalized.isin(indent_labels).map(
        {True: SALE_CHANNEL_INDENT_VALUE, False: SALE_CHANNEL_LOCAL_VALUE}
    )
    return out
