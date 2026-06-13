"""Analysis engine: filters, material/supplier normalization, period comparisons."""
from __future__ import annotations

import re
from typing import Literal

import numpy as np
import pandas as pd

from services.utils import generate_customer_registry

from config.settings import COL_BRAND_NAME, COL_SUPPLIER, COL_TYPE
from services.ml_columns import normalize_ml_column_names
from services.sale_channel_service import add_sale_channel_column

MONTH_ORDER = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
QUARTER_ORDER = {"q1": 1, "q2": 2, "q3": 3, "q4": 4}

CompareMode = Literal["yoy", "mom", "qoq", "ytd"]
AnalysisDimension = Literal["material", "type", "supplier"]

# Canonical supplier groups for Vietnam import dashboard
SUPPLIER_ALIASES = [
    ("Covestro", r"covestro"),
    ("Wanhua", r"wanhua"),
    ("Tosoh", r"tosoh"),
    ("Huntsman", r"huntsman"),
    ("BASF", r"basf"),
    ("Dow", r"\bdow\b"),
    ("Kumho Mitsui", r"kumho|mitsui"),
    ("Huafon", r"huafon"),
    ("KMC", r"\bkmc\b"),
    ("Sabic", r"sabic"),
    ("China Producer", r"china producer"),
    ("Korea Producer", r"korea producer"),
]


def ensure_numeric(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    for c in cols:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce")
    return out


def normalize_supplier_name(value) -> str:
    if pd.isna(value):
        return "Unknown"
    text = str(value).strip()
    if not text or text in (" ", "nan"):
        return "Unknown"
    upper = text.upper()
    for label, pattern in SUPPLIER_ALIASES:
        if re.search(pattern, upper, re.IGNORECASE):
            return label
    cleaned = text.title()
    if cleaned.upper() == "OTHER":
        return "Other"
    return cleaned


def normalize_material_type(value) -> str:
    """Map raw type strings to PMDI, MMDI, Prepolymer, ISO, Other."""
    if pd.isna(value):
        return "Unspecified"
    text = str(value).strip().upper()
    if not text or text in (" ", "NAN", "NONE"):
        return "Unspecified"
    if re.search(r"M\s*MDI|MMDI|MODIFIED\s*MDI", text):
        return "MMDI"
    if "PREPOLYMER" in text or "PRE POLYMER" in text:
        return "MDI Prepolymer"
    if re.search(r"P\s*MDI|PMDI", text):
        return "PMDI"
    if re.search(r"\bISO\b", text) and "POLYMER" not in text:
        return "ISO / Isocyanate"
    if "POLYURETHAN" in text or "PU" == text:
        return "Polyurethane"
    if "CRUDE" in text or "CRUDE MDI" in text:
        return "MDI Crude"
    return "Other specialty"


def prepare_analysis_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Add derived columns used by filters and charts."""
    out = normalize_ml_column_names(df)
    out = add_sale_channel_column(out)
    out = ensure_numeric(out, ["volume", "total_usd", "unit_price", "year"])
    if "date" in out.columns:
        out["date"] = pd.to_datetime(out["date"], errors="coerce")

    if "year" not in out.columns and "date" in out.columns:
        out["year"] = out["date"].dt.year

    if COL_SUPPLIER in out.columns:
        out["supplier_raw"] = out[COL_SUPPLIER].astype(str).str.strip()
        out.loc[out["supplier_raw"].isin(["", "nan", "NaN", "None"]), "supplier_raw"] = pd.NA
        out["supplier_group"] = out[COL_SUPPLIER].apply(normalize_supplier_name)
    else:
        out["supplier_raw"] = "Unknown"
        out["supplier_group"] = "Unknown"

    if COL_TYPE in out.columns:
        out["type_clean"] = out[COL_TYPE].astype(str).str.strip()
        out.loc[out["type_clean"].isin(["", "nan", "NaN", "None"]), "type_clean"] = pd.NA
        out["material_type"] = out[COL_TYPE].apply(normalize_material_type)
    else:
        out["type_clean"] = "Unspecified"
        out["material_type"] = "Unspecified"

    if COL_BRAND_NAME in out.columns:
        out["material"] = out[COL_BRAND_NAME].astype(str).str.strip()
    else:
        out["material"] = out.get("description", pd.Series(dtype=str)).astype(str).str.slice(0, 40)

    if "month" in out.columns:
        out["month"] = out["month"].astype(str).str.strip().str.lower()
        out["month_num"] = out["month"].map(MONTH_ORDER)
    if "quarter" in out.columns:
        out["quarter"] = out["quarter"].astype(str).str.strip().str.lower()
        out["quarter_num"] = out["quarter"].map(QUARTER_ORDER)

    return out


def resolve_type_column(df: pd.DataFrame) -> str:
    """Column used for Material type filter — raw file values in type_clean."""
    return "type_clean" if "type_clean" in df.columns else "material_type"


def filter_by_material_type(
    df: pd.DataFrame,
    material_type: str,
    *,
    type_col: str | None = None,
) -> pd.DataFrame:
    """
    Keep rows whose material type exactly matches the sidebar selection.

    Uses type_clean (raw TYPE from file), so e.g. PMDI excludes MODIFIED MDI,
    PMDI Prepolymer, and other distinct type_clean values in the MDI dataset.
    """
    if df.empty or material_type is None or not str(material_type).strip():
        return df.iloc[0:0].copy()
    col_name = type_col or resolve_type_column(df)
    if col_name not in df.columns:
        return df.iloc[0:0].copy()
    target = str(material_type).strip()
    mask = df[col_name].astype(str).str.strip() == target
    return df.loc[mask].copy()


def apply_dashboard_filters(
    df: pd.DataFrame,
    *,
    years: list | None = None,
    months: list | None = None,
    quarters: list | None = None,
    suppliers: list | None = None,
    material_types: list | None = None,
    materials: list | None = None,
    customers: list | None = None,
) -> pd.DataFrame:
    out = df.copy()
    if years and "year" in out.columns:
        out = out[out["year"].isin([int(y) for y in years])]
    if months and "month" in out.columns:
        out = out[out["month"].isin([str(m).lower() for m in months])]
    if quarters and "quarter" in out.columns:
        out = out[out["quarter"].isin([str(q).lower() for q in quarters])]
    if suppliers:
        if "supplier_raw" in out.columns:
            out = out[out["supplier_raw"].isin(suppliers)]
        elif "supplier_group" in out.columns:
            out = out[out["supplier_group"].isin(suppliers)]
    if material_types:
        col_name = resolve_type_column(out)
        if col_name in out.columns:
            target = {str(t).strip() for t in material_types}
            mask = out[col_name].astype(str).str.strip().isin(target)
            out = out.loc[mask]
    if materials and "material" in out.columns:
        out = out[out["material"].isin(materials)]
    if customers and "customer_id" in out.columns:
        out = out[out["customer_id"].isin(customers)]
    return out


def compute_kpis(df: pd.DataFrame, prior_df: pd.DataFrame | None = None) -> dict:
    df = ensure_numeric(df, ["volume", "total_usd", "unit_price"])
    kpis = {
        "total_orders": len(df),
        "unique_customers": int(df["customer_id"].nunique()) if "customer_id" in df.columns else 0,
        "unique_suppliers": int(df["supplier_group"].nunique()) if "supplier_group" in df.columns else 0,
        "unique_material_types": int(df["material_type"].nunique()) if "material_type" in df.columns else 0,
        "total_volume_kg": float(df["volume"].sum()) if "volume" in df.columns else 0.0,
        "total_usd": float(df["total_usd"].sum()) if "total_usd" in df.columns else 0.0,
        "avg_unit_price": float(df["unit_price"].mean()) if "unit_price" in df.columns else 0.0,
        "date_min": str(df["date"].min())[:10] if "date" in df.columns else "—",
        "date_max": str(df["date"].max())[:10] if "date" in df.columns else "—",
    }
    if prior_df is not None and len(prior_df) > 0:
        prior_df = ensure_numeric(prior_df, ["volume", "total_usd"])
        pv = float(prior_df["volume"].sum()) if "volume" in prior_df.columns else 0
        pu = float(prior_df["total_usd"].sum()) if "total_usd" in prior_df.columns else 0
        kpis["volume_change_pct"] = _pct_change(kpis["total_volume_kg"], pv)
        kpis["usd_change_pct"] = _pct_change(kpis["total_usd"], pu)
        kpis["orders_change_pct"] = _pct_change(kpis["total_orders"], len(prior_df))
    return kpis


def _pct_change(current: float, prior: float) -> float | None:
    if prior == 0 or prior is None:
        return None if current == 0 else 100.0
    return ((current - prior) / prior) * 100.0


def _slice_period(
    df: pd.DataFrame,
    year: int,
    months: list[str] | None = None,
    quarters: list[str] | None = None,
) -> pd.DataFrame:
    out = df[df["year"] == year] if "year" in df.columns else df.iloc[0:0]
    if months and "month" in out.columns:
        out = out[out["month"].isin(months)]
    if quarters and "quarter" in out.columns:
        out = out[out["quarter"].isin(quarters)]
    return out


def _ytd_months_through(month: str) -> list[str]:
    n = MONTH_ORDER.get(month.lower(), 12)
    inv = {v: k for k, v in MONTH_ORDER.items()}
    return [inv[i] for i in range(1, n + 1) if i in inv]


def build_comparison_frames(
    df: pd.DataFrame,
    mode: CompareMode,
    *,
    anchor_year: int | None = None,
    anchor_month: str | None = None,
    anchor_quarter: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    """
    Return (current_period_df, prior_period_df, comparison_label).
    """
    if "year" not in df.columns or df["year"].isna().all():
        empty = df.iloc[0:0]
        return empty, empty, "No year column"

    years = sorted(int(y) for y in df["year"].dropna().unique())
    anchor_year = int(anchor_year or years[-1])

    if mode == "yoy":
        prior_year = anchor_year - 1
        months = [anchor_month] if anchor_month else None
        quarters = [anchor_quarter] if anchor_quarter else None
        current = _slice_period(df, anchor_year, months=months, quarters=quarters)
        prior = _slice_period(df, prior_year, months=months, quarters=quarters)
        label = f"YoY · {anchor_year} vs {prior_year}"
        if anchor_month:
            label += f" · {anchor_month.upper()}"
        if anchor_quarter:
            label += f" · {anchor_quarter.upper()}"
        return current, prior, label

    if mode == "mom":
        if not anchor_month and anchor_year in years:
            sub = df[df["year"] == anchor_year]
            if "month_num" in sub.columns and sub["month_num"].notna().any():
                anchor_month = sub.loc[sub["month_num"].idxmax(), "month"]
        month = (anchor_month or "dec").lower()
        mnum = MONTH_ORDER.get(month, 12)
        prior_month = {v: k for k, v in MONTH_ORDER.items()}.get(mnum - 1, "dec")
        prior_year = anchor_year if mnum > 1 else anchor_year - 1
        current = _slice_period(df, anchor_year, months=[month])
        prior = _slice_period(df, prior_year, months=[prior_month])
        return current, prior, f"MoM · {month.upper()} {anchor_year} vs {prior_month.upper()} {prior_year}"

    if mode == "qoq":
        quarter = (anchor_quarter or "q4").lower()
        qnum = QUARTER_ORDER.get(quarter, 4)
        prior_q = {v: k for k, v in QUARTER_ORDER.items()}.get(qnum - 1, "q4")
        prior_year = anchor_year if qnum > 1 else anchor_year - 1
        current = _slice_period(df, anchor_year, quarters=[quarter])
        prior = _slice_period(df, prior_year, quarters=[prior_q])
        return current, prior, f"QoQ · {quarter.upper()} {anchor_year} vs {prior_q.upper()} {prior_year}"

    if mode == "ytd":
        if not anchor_month and anchor_year in years:
            sub = df[df["year"] == anchor_year]
            if "month_num" in sub.columns and sub["month_num"].notna().any():
                anchor_month = sub.loc[sub["month_num"].idxmax(), "month"]
        month = (anchor_month or "dec").lower()
        ytd_months = _ytd_months_through(month)
        current = _slice_period(df, anchor_year, months=ytd_months)
        prior = _slice_period(df, anchor_year - 1, months=ytd_months)
        return current, prior, f"YTD through {month.upper()} · {anchor_year} vs {anchor_year - 1}"

    return df, df.iloc[0:0], mode


def aggregate_metric(
    df: pd.DataFrame,
    group_col: str,
    metrics: list[str] | None = None,
) -> pd.DataFrame:
    metrics = metrics or ["volume", "total_usd"]
    cols = [c for c in metrics if c in df.columns]
    if group_col not in df.columns or not cols:
        return pd.DataFrame()
    return df.groupby(group_col, dropna=False)[cols].sum().reset_index()


def time_series_by_period(
    df: pd.DataFrame,
    period_col: str,
    group_col: str | None = None,
    value_col: str = "total_usd",
) -> pd.DataFrame:
    if period_col not in df.columns or value_col not in df.columns:
        return pd.DataFrame()
    df = ensure_numeric(df, [value_col])
    if group_col and group_col in df.columns:
        out = df.groupby([period_col, group_col], dropna=False)[value_col].sum().reset_index()
    else:
        out = df.groupby(period_col, dropna=False)[value_col].sum().reset_index()
    if period_col == "month" and "month_num" in df.columns:
        order = df[[period_col, "month_num"]].drop_duplicates().sort_values("month_num")
        cat = order[period_col].tolist()
        out[period_col] = pd.Categorical(out[period_col], categories=cat, ordered=True)
        out = out.sort_values(period_col)
    return out


def comparison_by_dimension(
    current: pd.DataFrame,
    prior: pd.DataFrame,
    dimension: str,
    value_col: str = "total_usd",
    top_n: int = 12,
) -> pd.DataFrame:
    dim_map = {
        "material": "material",
        "type": "material_type",
        "supplier": "supplier_group",
    }
    col = dim_map.get(dimension, dimension)
    if col not in current.columns:
        return pd.DataFrame()

    cur = aggregate_metric(current, col, [value_col]).rename(columns={value_col: "current"})
    prv = aggregate_metric(prior, col, [value_col]).rename(columns={value_col: "prior"})
    merged = cur.merge(prv, on=col, how="outer").fillna(0)
    merged["change_pct"] = merged.apply(
        lambda r: _pct_change(r["current"], r["prior"]), axis=1
    )
    merged["change_abs"] = merged["current"] - merged["prior"]
    return merged.sort_values("current", ascending=False).head(top_n)


def supplier_market_share(df: pd.DataFrame, value_col: str = "total_usd") -> pd.DataFrame:
    if "supplier_group" not in df.columns:
        return pd.DataFrame()
    agg = aggregate_metric(df, "supplier_group", [value_col])
    total = agg[value_col].sum()
    if total == 0:
        return agg
    agg["share_pct"] = (agg[value_col] / total * 100).round(1)
    return agg.sort_values(value_col, ascending=False)


def material_type_mix(df: pd.DataFrame, value_col: str = "total_usd") -> pd.DataFrame:
    if "material_type" not in df.columns:
        return pd.DataFrame()
    agg = aggregate_metric(df, "material_type", [value_col])
    total = agg[value_col].sum()
    if total == 0:
        return agg
    agg["share_pct"] = (agg[value_col] / total * 100).round(1)
    return agg.sort_values(value_col, ascending=False)


def top_materials(df: pd.DataFrame, n: int = 15, value_col: str = "total_usd") -> pd.DataFrame:
    if "material" not in df.columns:
        return pd.DataFrame()
    return (
        aggregate_metric(df, "material", [value_col, "volume"])
        .sort_values(value_col, ascending=False)
        .head(n)
    )


def filter_options(df: pd.DataFrame) -> dict:
    """Unique values for UI multiselects."""
    opts = {}
    if "year" in df.columns:
        opts["years"] = sorted(int(y) for y in df["year"].dropna().unique())
    if "month" in df.columns:
        opts["months"] = sorted(
            [str(m).lower() for m in df["month"].dropna().unique()],
            key=lambda m: MONTH_ORDER.get(m, 99),
        )
    if "quarter" in df.columns:
        opts["quarters"] = sorted(
            [str(q).lower() for q in df["quarter"].dropna().unique()],
            key=lambda q: QUARTER_ORDER.get(q, 99),
        )
    if "supplier_raw" in df.columns:
        opts["suppliers"] = sorted(
            [s for s in df["supplier_raw"].dropna().unique() if str(s).strip()],
            key=str,
        )
    elif "supplier_group" in df.columns:
        opts["suppliers"] = sorted(df["supplier_group"].dropna().unique())
    if "type_clean" in df.columns:
        opts["material_types"] = sorted(
            [t for t in df["type_clean"].dropna().unique() if str(t).strip()],
            key=str,
        )
    elif "type" in df.columns:
        opts["material_types"] = sorted(
            df["type"].dropna().astype(str).str.strip().unique().tolist(),
            key=str,
        )
    elif "material_type" in df.columns:
        opts["material_types"] = sorted(df["material_type"].dropna().unique())
    if "material" in df.columns:
        top_m = (
            df.groupby("material")["total_usd"].sum().sort_values(ascending=False).head(30).index
            if "total_usd" in df.columns
            else df["material"].value_counts().head(30).index
        )
        opts["materials"] = list(top_m)
    if "customer_name" in df.columns:
        opts["customers"] = sorted(df["customer_name"].dropna().unique().tolist())[:50]
    return opts


def build_customer_registry(df: pd.DataFrame) -> pd.DataFrame:
    required = {"customer_id", "customer_name", "year"}
    if not required.issubset(df.columns):
        return pd.DataFrame()
    return generate_customer_registry(df)
