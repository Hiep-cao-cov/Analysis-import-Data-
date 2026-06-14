"""Classify saler as DIRECT (supplier) vs INDIRECT (trader/distributor) via regex."""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from config.settings import (
    MDI_HS_CODES,
    MDI_PMDI_SUPPLIER_LIST,
    TDI_HS_CODES,
    TDI_TDI_SUPPLIER_LIST,
    TYPE_SALE_COLUMN,
    TYPE_SALE_DIRECT,
    TYPE_SALE_FILTER_ALL,
    TYPE_SALE_INDIRECT,
    TYPE_SALE_SUPPLIER_PATTERNS,
)

_SALER_COLUMN = "saler"


def product_line_for_hs_codes(
    hs_codes: list[str] | None = None,
    *,
    path: Path | str | None = None,
) -> str:
    """Return MDI or TDI from HS filter list or dataset filename."""
    if hs_codes:
        if set(hs_codes) == set(TDI_HS_CODES):
            return "TDI"
        return "MDI"
    if path is not None:
        name = Path(path).name.lower()
        if "pmdi" in name or "mdi" in name:
            return "MDI"
        if "tdi" in name:
            return "TDI"
    return "MDI"


def supplier_list_for_product_line(product_line: str) -> tuple[str, ...]:
    """Curated supplier names used to detect direct sales (excludes OTHER)."""
    line = str(product_line).strip().upper()
    if line == "TDI":
        source = TDI_TDI_SUPPLIER_LIST
    else:
        source = MDI_PMDI_SUPPLIER_LIST
    return tuple(s for s in source if str(s).strip().upper() != "OTHER")


@lru_cache(maxsize=4)
def _compiled_supplier_patterns(product_line: str) -> tuple[tuple[str, re.Pattern[str]], ...]:
    patterns: list[tuple[str, re.Pattern[str]]] = []
    for supplier in supplier_list_for_product_line(product_line):
        label = str(supplier).strip().upper()
        if not label:
            continue
        custom = TYPE_SALE_SUPPLIER_PATTERNS.get(label) or TYPE_SALE_SUPPLIER_PATTERNS.get(
            label.title()
        )
        if custom:
            pat = re.compile(custom, re.IGNORECASE)
        else:
            pat = re.compile(re.escape(label), re.IGNORECASE)
        patterns.append((label, pat))
    return tuple(patterns)


def saler_matches_supplier(saler, *, product_line: str = "MDI") -> bool:
    """
    True when standardized saler text contains a supplier name (regex match).
  """
    text = str(saler).strip()
    if not text or text.lower() in ("nan", "none"):
        return False
    for _, pattern in _compiled_supplier_patterns(product_line):
        if pattern.search(text):
            return True
    return False


def apply_type_sale_column(
    df: pd.DataFrame,
    *,
    product_line: str = "MDI",
) -> pd.DataFrame:
    """
    Add column `type_sale`:
    - DIRECT   — saler name matches a supplier in MDI_PMDI_SUPPLIER_LIST or TDI_TDI_SUPPLIER_LIST
    - INDIRECT — otherwise (trader / distributor)
    """
    if df.empty or _SALER_COLUMN not in df.columns:
        return df

    out = df.copy()
    line = str(product_line).strip().upper() or "MDI"
    is_direct = out[_SALER_COLUMN].map(lambda value: saler_matches_supplier(value, product_line=line))
    out[TYPE_SALE_COLUMN] = np.where(is_direct, TYPE_SALE_DIRECT, TYPE_SALE_INDIRECT)
    return out


def filter_by_type_sale(df: pd.DataFrame, type_sale: str | None) -> pd.DataFrame:
    """Keep rows matching DIRECT / INDIRECT; All (or empty) keeps every row."""
    if df.empty or TYPE_SALE_COLUMN not in df.columns:
        return df.copy()

    choice = str(type_sale or TYPE_SALE_FILTER_ALL).strip().upper()
    if not choice or choice == TYPE_SALE_FILTER_ALL.upper():
        return df.copy()

    mask = df[TYPE_SALE_COLUMN].astype(str).str.strip().str.upper() == choice
    return df.loc[mask].copy()
