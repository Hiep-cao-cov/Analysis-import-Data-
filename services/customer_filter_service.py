"""Customer sidebar options and scoped frames for Tab 3 customer deep dive."""

from __future__ import annotations

import pandas as pd

from config.settings import CUSTOMER_FILTER_TOP_N
from services.analysis_service import filter_by_material_type, resolve_type_column
from services.sale_channel_service import filter_by_sale_channel
from services.supplier_filter_service import prepare_supplier_analysis_frame


def normalize_customer_id(value) -> str:
    return str(value).strip()


def resolve_customer_col(df: pd.DataFrame) -> str:
    if "customer_id" in df.columns:
        return "customer_id"
    if "customer_name" in df.columns:
        return "customer_name"
    return "customer_id"


def _scoped_material_frame(
    df: pd.DataFrame,
    *,
    material_type: str,
    sale_channel: str,
    type_col: str | None = None,
) -> pd.DataFrame:
    type_col = type_col or resolve_type_column(df)
    scoped = filter_by_sale_channel(df, sale_channel)
    return filter_by_material_type(scoped, material_type, type_col=type_col)


def _customer_name_lookup(scoped: pd.DataFrame, customer_col: str) -> dict[str, str]:
    if scoped.empty or customer_col not in scoped.columns:
        return {}
    if customer_col == "customer_id" and "customer_name" in scoped.columns:
        pairs = (
            scoped[["customer_id", "customer_name"]]
            .dropna(subset=["customer_id"])
            .astype({"customer_id": str, "customer_name": str})
        )
        pairs["customer_id"] = pairs["customer_id"].str.strip()
        pairs["customer_name"] = pairs["customer_name"].str.strip()
        pairs = pairs[pairs["customer_id"] != ""]
        lookup: dict[str, str] = {}
        for cid, rows in pairs.groupby("customer_id"):
            names = rows["customer_name"].tolist()
            lookup[cid] = max(names, key=len) if names else cid
        return lookup
    names = scoped[customer_col].dropna().astype(str).str.strip()
    names = names[names != ""]
    return {name: name for name in names.unique().tolist()}


def resolve_customer_filter_options(
    df: pd.DataFrame,
    *,
    material_type: str,
    sale_channel: str,
    type_col: str | None = None,
    year: int | None = None,
    top_n: int = CUSTOMER_FILTER_TOP_N,
    ensure_ids: list[str] | None = None,
) -> list[tuple[str, str]]:
    """
    Return (customer_id, customer_name) pairs sorted by volume desc (top N).
    Uses customer_id when available; otherwise customer_name as both key and label.
    """
    if df.empty or not str(material_type).strip():
        return []

    type_col = type_col or resolve_type_column(df)
    scoped = _scoped_material_frame(
        df,
        material_type=material_type,
        sale_channel=sale_channel,
        type_col=type_col,
    )
    customer_col = resolve_customer_col(scoped)
    if scoped.empty or customer_col not in scoped.columns or "volume_ton" not in scoped.columns:
        return []

    work = scoped.copy()
    if year is not None and "year" in work.columns:
        work["year"] = pd.to_numeric(work["year"], errors="coerce")
        work = work[work["year"] == year]

    work[customer_col] = work[customer_col].astype(str).str.strip()
    work = work[work[customer_col] != ""]
    if work.empty:
        return []

    name_lookup = _customer_name_lookup(scoped, customer_col)
    ranked = (
        work.groupby(customer_col, dropna=False)["volume_ton"]
        .sum()
        .reset_index()
        .sort_values("volume_ton", ascending=False)
    )

    result: list[tuple[str, str]] = []
    seen: set[str] = set()
    for _, row in ranked.head(top_n).iterrows():
        cid = normalize_customer_id(row[customer_col])
        if cid in seen:
            continue
        seen.add(cid)
        result.append((cid, name_lookup.get(cid, cid)))

    for cid in ensure_ids or []:
        key = normalize_customer_id(cid)
        if key and key not in seen:
            seen.add(key)
            result.append((key, name_lookup.get(key, key)))

    return result


def default_customer_id(
    df: pd.DataFrame,
    *,
    material_type: str,
    sale_channel: str,
    year: int | None = None,
) -> str | None:
    """First customer_id by volume in the active Tab 3 filter scope (must have data)."""
    options = resolve_customer_filter_options(
        df,
        material_type=material_type,
        sale_channel=sale_channel,
        year=year,
    )
    return options[0][0] if options else None


def customer_id_to_name(options: list[tuple[str, str]]) -> dict[str, str]:
    return {cid: name for cid, name in options}


def filter_by_customer(
    df: pd.DataFrame,
    customer_id: str,
    *,
    customer_col: str | None = None,
) -> pd.DataFrame:
    if df.empty:
        return df
    col = customer_col or resolve_customer_col(df)
    if col not in df.columns:
        return df.iloc[0:0].copy()
    sel = normalize_customer_id(customer_id)
    mask = df[col].astype(str).str.strip() == sel
    return df.loc[mask].copy()


def prepare_customer_analysis_frame(
    df: pd.DataFrame,
    *,
    dataset_label: str,
    material_type: str,
    sale_channel: str,
    type_col: str | None = None,
    supplier_col: str = "supplier_raw",
) -> pd.DataFrame:
    """Sale-channel scoped frame with curated supplier grouping for mix charts."""
    return prepare_supplier_analysis_frame(
        df,
        dataset_label=dataset_label,
        material_type=material_type,
        sale_channel=sale_channel,
        type_col=type_col,
        supplier_col=supplier_col,
    )
