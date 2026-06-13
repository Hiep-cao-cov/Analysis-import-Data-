"""Map customer_id → short_name using app_config/customer_list.csv."""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from pathlib import Path

import pandas as pd

from config.settings import CUSTOMER_LIST_FILE


def normalize_customer_id(value) -> str:
    """
    Normalize IDs for join (strip, drop Excel .0 suffix).
    Vietnamese tax IDs: align 9-digit and 10-digit forms (leading zero).
    """
    text = str(value).strip()
    if text.endswith(".0"):
        stem = text[:-2]
        if stem.replace("-", "").isdigit():
            text = stem
    digits = text.replace("-", "")
    if digits.isdigit():
        # Ma doanh nghiep is often stored as 0900187865 vs 900187865
        if len(digits) <= 10:
            return digits.zfill(10)
        return digits
    return text


def normalize_customer_name(value) -> str:
    """Normalize company name for fallback matching."""
    text = unicodedata.normalize("NFC", str(value).strip().lower())
    return re.sub(r"\s+", " ", text).strip()


def _resolve_column(columns: set[str], *candidates: str) -> str | None:
    for name in candidates:
        if name in columns:
            return name
    return None


@lru_cache(maxsize=1)
def load_customer_short_name_lookup(path: str | None = None) -> tuple[dict[str, str], dict[str, str]]:
    """
    Load lookup tables from customer_list.csv.
    Returns (id_to_short, normalized_full_name_to_short).
    Indexes customer_id, rcode, pcode, and similar alias columns per row.
    """
    list_path = Path(path) if path else CUSTOMER_LIST_FILE
    if not list_path.is_file():
        return {}, {}

    df = pd.read_csv(list_path, encoding="utf-8-sig", low_memory=False)
    df.columns = [str(c).strip().lower() for c in df.columns]
    cols = set(df.columns)

    short_col = _resolve_column(cols, "short_name", "short name")
    name_col = _resolve_column(cols, "customer", "full name of customer", "full_name")
    id_cols = [
        c
        for c in ("customer_id", "custome_id", "rcode", "pcode")
        if c in cols
    ]
    if not short_col or not id_cols:
        return {}, {}

    id_to_short: dict[str, str] = {}
    name_to_short: dict[str, str] = {}

    for row in df.itertuples(index=False):
        row_dict = row._asdict()
        short = str(row_dict.get(short_col, "")).strip()
        if not short or short.lower() in ("nan", "none"):
            continue
        for id_col in id_cols:
            raw_id = row_dict.get(id_col)
            if pd.isna(raw_id):
                continue
            key = normalize_customer_id(raw_id)
            if key:
                id_to_short[key] = short
        if name_col:
            raw_name = row_dict.get(name_col)
            if pd.notna(raw_name) and str(raw_name).strip():
                name_to_short[normalize_customer_name(raw_name)] = short

    return id_to_short, name_to_short


@lru_cache(maxsize=1)
def load_customer_short_name_map(path: str | None = None) -> dict[str, str]:
    """Backward-compatible: id → short_name map only."""
    id_map, _ = load_customer_short_name_lookup(path)
    return id_map


def _resolve_short_name(
    customer_id,
    customer_name,
    *,
    id_to_short: dict[str, str],
    name_to_short: dict[str, str],
) -> str | None:
    key = normalize_customer_id(customer_id)
    short = id_to_short.get(key)
    if short:
        return short
    norm_name = normalize_customer_name(customer_name)
    return name_to_short.get(norm_name)


def apply_customer_short_names(
    df: pd.DataFrame,
    *,
    mapping: dict[str, str] | None = None,
    list_path: str | Path | None = None,
) -> pd.DataFrame:
    """
    Replace customer_name with short_name where customer_id or full name matches.
    Unmatched rows keep the existing customer_name.
    """
    if df.empty or "customer_id" not in df.columns or "customer_name" not in df.columns:
        return df

    if mapping is not None:
        id_to_short = mapping
        name_to_short: dict[str, str] = {}
    else:
        id_to_short, name_to_short = load_customer_short_name_lookup(
            str(list_path) if list_path else None
        )
    if not id_to_short and not name_to_short:
        return df

    out = df.copy()
    resolved = [
        _resolve_short_name(r.customer_id, r.customer_name, id_to_short=id_to_short, name_to_short=name_to_short)
        for r in out.itertuples(index=False)
    ]
    mask = pd.Series([s is not None and str(s).strip() != "" for s in resolved], index=out.index)
    if mask.any():
        out.loc[mask, "customer_name"] = [s for s, m in zip(resolved, mask, strict=False) if m and s]
    return out


def reload_customer_short_name_map() -> dict[str, str]:
    """Clear cache after customer_list.csv is updated."""
    load_customer_short_name_lookup.cache_clear()
    load_customer_short_name_map.cache_clear()
    return load_customer_short_name_map()


def find_unmapped_customers(
    df: pd.DataFrame,
    *,
    mapping: dict[str, str] | None = None,
) -> pd.DataFrame:
    """
    Customers not matched by customer_id or normalized full name in customer_list.csv.
    """
    empty = pd.DataFrame(columns=["customer_id", "full_name", "import_rows", "short_name"])
    if df.empty or "customer_id" not in df.columns or "customer_name" not in df.columns:
        return empty

    if mapping is not None:
        id_to_short = mapping
        name_to_short = {}
    else:
        id_to_short, name_to_short = load_customer_short_name_lookup()

    work = df[["customer_id", "customer_name"]].copy()
    work["customer_id"] = work["customer_id"].map(normalize_customer_id)
    work["customer_name"] = work["customer_name"].astype(str).str.strip()
    work = work[(work["customer_id"] != "") & (work["customer_name"] != "")]

    def is_mapped(row) -> bool:
        if _resolve_short_name(row.customer_id, row.customer_name, id_to_short=id_to_short, name_to_short=name_to_short):
            return True
        return False

    mapped_mask = work.apply(is_mapped, axis=1)
    unmapped = work[~mapped_mask]
    if unmapped.empty:
        return empty

    summary = (
        unmapped.groupby("customer_id", as_index=False)
        .agg(full_name=("customer_name", "first"), import_rows=("customer_id", "count"))
        .sort_values("import_rows", ascending=False)
    )
    summary["short_name"] = ""
    return summary.reset_index(drop=True)


def append_customers_to_list(
    entries: pd.DataFrame,
    *,
    list_path: Path | None = None,
) -> tuple[int, int]:
    """
    Append new rows to customer_list.csv.
    entries: customer_id, short_name, optional full_name.
    Returns (added_count, skipped_duplicate_count).
    """
    path = Path(list_path) if list_path else CUSTOMER_LIST_FILE
    if entries.empty:
        return 0, 0

    required = {"customer_id", "short_name"}
    if not required.issubset(entries.columns):
        raise ValueError("entries must include customer_id and short_name")

    work = entries.copy()
    work["customer_id"] = work["customer_id"].map(normalize_customer_id)
    work["short_name"] = work["short_name"].astype(str).str.strip()
    if "full_name" in work.columns:
        work["full_name"] = work["full_name"].astype(str).str.strip()
    else:
        work["full_name"] = ""

    work = work[
        (work["customer_id"] != "")
        & (work["short_name"] != "")
        & (~work["short_name"].isin(["nan", "NaN", "None"]))
    ]
    if work.empty:
        return 0, 0

    if path.is_file():
        existing = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
        existing_ids = {
            normalize_customer_id(v)
            for v in existing.get("customer_id", existing.iloc[:, 0]).dropna()
        }
    else:
        existing = pd.DataFrame(
            columns=[
                "customer_id", "RCode", "Customer", "short_name",
                "Industry", "Mat", "PNR", "Location", "Invester",
                "Chanel", "Supplier", "Address", "Note",
            ]
        )
        existing_ids = set()

    new_rows: list[dict] = []
    skipped = 0
    for row in work.itertuples(index=False):
        cid = row.customer_id
        if cid in existing_ids:
            skipped += 1
            continue
        full = getattr(row, "full_name", "") or ""
        new_rows.append(
            {
                "customer_id": cid,
                "RCode": cid,
                "Customer": full,
                "short_name": row.short_name,
            }
        )
        existing_ids.add(cid)

    if not new_rows:
        return 0, skipped

    append_df = pd.DataFrame(new_rows)
    for col in existing.columns:
        if col not in append_df.columns:
            append_df[col] = ""
    append_df = append_df[existing.columns]
    combined = pd.concat([existing, append_df], ignore_index=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(path, index=False, encoding="utf-8-sig")
    reload_customer_short_name_map()
    return len(new_rows), skipped
