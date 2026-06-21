"""Analysis engine: filters, material/supplier normalization for dashboards."""
from __future__ import annotations

import re

import pandas as pd

from config.settings import COL_BRAND_NAME, COL_SUPPLIER, COL_TYPE
from services.ml_columns import normalize_ml_column_names
from services.sale_channel_service import add_sale_channel_column

MONTH_ORDER = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
QUARTER_ORDER = {"q1": 1, "q2": 2, "q3": 3, "q4": 4}

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

    if "date" in out.columns:
        dates = out["date"]
        if "month" in out.columns:
            month_missing = (
                out["month"].astype(str).str.strip().replace({"nan": "", "NaN": "", "None": ""}) == ""
            )
            if month_missing.any():
                out.loc[month_missing, "month"] = (
                    dates.loc[month_missing].dt.strftime("%b").str.lower()
                )
        else:
            out["month"] = dates.dt.strftime("%b").str.lower()

        if "quarter" in out.columns:
            quarter_missing = (
                out["quarter"].astype(str).str.strip().replace({"nan": "", "NaN": "", "None": ""}) == ""
            )
            if quarter_missing.any():
                out.loc[quarter_missing, "quarter"] = (
                    "q" + dates.loc[quarter_missing].dt.quarter.astype("Int64").astype(str)
                )
        else:
            out["quarter"] = "q" + dates.dt.quarter.astype(str)

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
