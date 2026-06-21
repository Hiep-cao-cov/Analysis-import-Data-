"""Supplier sidebar lists and curated grouping for market/supplier analysis."""

from __future__ import annotations

import pandas as pd

from config.settings import (
    CURATED_SUPPLIER_FILTER_RULES,
    SUPPLIER_MIN_AVG_MARKET_SHARE_PCT,
)
from services.analysis_service import filter_by_material_type, resolve_type_column
from services.sale_channel_service import filter_by_sale_channel


def supplier_filter_key(name: str) -> str:
    return str(name).strip().upper()


def get_curated_supplier_list(dataset_label: str, material_type: str) -> list[str] | None:
    """Return fixed supplier list for dataset + material type, or None for dynamic rule."""
    dataset_key = str(dataset_label).strip().upper()
    if dataset_key == "PMDI":
        dataset_key = "MDI"
    material_key = str(material_type).strip().upper()
    return CURATED_SUPPLIER_FILTER_RULES.get((dataset_key, material_key))


def _canonical_curated_name(config_name: str, curated_list: list[str]) -> str:
    key = supplier_filter_key(config_name)
    for name in curated_list:
        if supplier_filter_key(name) == key:
            return str(name).strip().upper() if key != "OTHER" else "OTHER"
    return str(config_name).strip().upper()


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


def _curated_names_with_data(
    scoped: pd.DataFrame,
    curated_list: list[str],
    supplier_col: str,
) -> list[str]:
    """Config order; hide entries with no volume except OTHER (always shown)."""
    if scoped.empty or supplier_col not in scoped.columns:
        return ["OTHER"] if any(supplier_filter_key(s) == "OTHER" for s in curated_list) else []

    data_keys = {
        supplier_filter_key(name)
        for name in scoped[supplier_col].dropna().astype(str).tolist()
        if str(name).strip()
    }
    vol_by_key: dict[str, float] = (
        scoped.groupby(scoped[supplier_col].astype(str).str.strip().str.upper())["volume_ton"]
        .sum()
        .to_dict()
        if "volume_ton" in scoped.columns
        else {}
    )

    result: list[str] = []
    for config_name in curated_list:
        key = supplier_filter_key(config_name)
        if key == "OTHER":
            result.append(_canonical_curated_name(config_name, curated_list))
            continue
        has_data = key in data_keys and float(vol_by_key.get(key, 0.0)) > 0.0
        if has_data:
            result.append(_canonical_curated_name(config_name, curated_list))

    if not any(supplier_filter_key(name) == "OTHER" for name in result):
        for config_name in curated_list:
            if supplier_filter_key(config_name) == "OTHER":
                result.append(_canonical_curated_name(config_name, curated_list))
                break
    return result


def suppliers_by_avg_market_share(
    df: pd.DataFrame,
    *,
    material_type: str,
    sale_channel: str,
    type_col: str | None = None,
    supplier_col: str = "supplier_raw",
    min_avg_share_pct: float = SUPPLIER_MIN_AVG_MARKET_SHARE_PCT,
) -> list[str]:
    """MDI non-PMDI rule: suppliers whose average yearly market share exceeds min_avg_share_pct."""
    scoped = _scoped_material_frame(
        df,
        material_type=material_type,
        sale_channel=sale_channel,
        type_col=type_col,
    )
    if scoped.empty or "year" not in scoped.columns or supplier_col not in scoped.columns:
        return []

    scoped = scoped.copy()
    scoped["year"] = pd.to_numeric(scoped["year"], errors="coerce")
    scoped = scoped.dropna(subset=["year"])
    if scoped.empty:
        return []

    share_samples: dict[str, list[float]] = {}
    for year, year_df in scoped.groupby(scoped["year"].astype(int)):
        market_ton = float(year_df["volume_ton"].sum()) if "volume_ton" in year_df.columns else 0.0
        if market_ton <= 0:
            continue
        by_supplier = (
            year_df.groupby(supplier_col, dropna=False)["volume_ton"]
            .sum()
            .reset_index()
        )
        for _, row in by_supplier.iterrows():
            supplier_name = str(row[supplier_col]).strip()
            if not supplier_name:
                continue
            share_pct = float(row["volume_ton"]) / market_ton * 100.0
            share_samples.setdefault(supplier_name, []).append(share_pct)

    ranked: list[tuple[str, float]] = []
    for supplier_name, samples in share_samples.items():
        if not samples:
            continue
        avg_share = sum(samples) / len(samples)
        if avg_share > min_avg_share_pct:
            ranked.append((supplier_name.strip().upper(), avg_share))

    ranked.sort(key=lambda item: (-item[1], item[0]))
    return [name for name, _ in ranked]


def _supplier_names_from_scope(
    scoped: pd.DataFrame,
    supplier_col: str,
) -> list[str]:
    if scoped.empty or supplier_col not in scoped.columns:
        return []
    return sorted(
        {str(s).strip().upper() for s in scoped[supplier_col].dropna().unique() if str(s).strip()},
        key=str,
    )


def resolve_supplier_filter_options(
    df: pd.DataFrame,
    *,
    dataset_label: str,
    material_type: str,
    sale_channel: str,
    type_col: str | None = None,
    supplier_col: str = "supplier_raw",
) -> list[str]:
    """Supplier selectbox options for Tab 1 & Tab 2 shared filters."""
    if df.empty or not str(material_type).strip():
        return []

    type_col = type_col or resolve_type_column(df)
    curated = get_curated_supplier_list(dataset_label, material_type)
    if curated:
        scoped = _scoped_material_frame(
            df,
            material_type=material_type,
            sale_channel=sale_channel,
            type_col=type_col,
        )
        names = _curated_names_with_data(scoped, curated, supplier_col)
        if names:
            return names
        fallback = _supplier_names_from_scope(scoped, supplier_col)
        return fallback if fallback else names

    dataset_key = str(dataset_label).strip().upper()
    if dataset_key == "PMDI":
        dataset_key = "MDI"
    material_key = str(material_type).strip().upper()
    if dataset_key == "MDI" and material_key != "PMDI":
        names = suppliers_by_avg_market_share(
            df,
            material_type=material_type,
            sale_channel=sale_channel,
            type_col=type_col,
            supplier_col=supplier_col,
        )
        if names:
            return names
        scoped = _scoped_material_frame(
            df,
            material_type=material_type,
            sale_channel=sale_channel,
            type_col=type_col,
        )
        return _supplier_names_from_scope(scoped, supplier_col)

    scoped = _scoped_material_frame(
        df,
        material_type=material_type,
        sale_channel=sale_channel,
        type_col=type_col,
    )
    if scoped.empty or supplier_col not in scoped.columns:
        return []
    return _supplier_names_from_scope(scoped, supplier_col)


def apply_curated_supplier_grouping(
    df: pd.DataFrame,
    curated_list: list[str],
    *,
    supplier_col: str = "supplier_raw",
) -> pd.DataFrame:
    """Roll non-curated suppliers into OTHER; keeps market totals complete."""
    if df.empty or supplier_col not in df.columns or not curated_list:
        return df

    out = df.copy()
    curated_keys = {
        supplier_filter_key(name)
        for name in curated_list
        if supplier_filter_key(name) != "OTHER"
    }
    other_name = next(
        (_canonical_curated_name(name, curated_list) for name in curated_list if supplier_filter_key(name) == "OTHER"),
        "OTHER",
    )
    canonical_by_key = {
        supplier_filter_key(name): _canonical_curated_name(name, curated_list)
        for name in curated_list
        if supplier_filter_key(name) != "OTHER"
    }

    def _remap(value) -> str:
        key = supplier_filter_key(value)
        if key in curated_keys:
            return canonical_by_key.get(key, str(value).strip().upper())
        return other_name

    out[supplier_col] = out[supplier_col].apply(_remap)
    return out


def prepare_supplier_analysis_frame(
    df: pd.DataFrame,
    *,
    dataset_label: str,
    material_type: str,
    sale_channel: str,
    type_col: str | None = None,
    supplier_col: str = "supplier_raw",
) -> pd.DataFrame:
    """
    Sale-channel scoped frame. For curated supplier rules, remap non-listed suppliers to OTHER
    on rows matching the selected material type only.
    """
    type_col = type_col or resolve_type_column(df)
    out = filter_by_sale_channel(df, sale_channel)
    curated = get_curated_supplier_list(dataset_label, material_type)
    if not curated:
        return out

    material_rows = filter_by_material_type(out, material_type, type_col=type_col)
    if material_rows.empty:
        return out

    grouped = apply_curated_supplier_grouping(material_rows, curated, supplier_col=supplier_col)
    out = out.copy()
    out.loc[grouped.index, supplier_col] = grouped[supplier_col].values
    return out
