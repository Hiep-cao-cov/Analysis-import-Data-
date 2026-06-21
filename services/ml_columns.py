"""Canonical ML / analytics column names (name-based, not position)."""
from __future__ import annotations

import pandas as pd

from config.settings import COL_BRAND_NAME, COL_SUPPLIER, COL_TYPE

# Case-insensitive aliases → canonical name
_TARGET_ALIASES: dict[str, str] = {
    "brand name": COL_BRAND_NAME,
    "brand_name": COL_BRAND_NAME,
    "brandname": COL_BRAND_NAME,
    "label": COL_BRAND_NAME,
    "supplier": COL_SUPPLIER,
    "type": COL_TYPE,
    "material type": COL_TYPE,
    "material_type": COL_TYPE,
}

_PREDICTION_ALIASES: dict[str, str] = {
    "predicted_label": COL_BRAND_NAME,
    "predicted brand name": COL_BRAND_NAME,
    "predicted_brand name": COL_BRAND_NAME,
    "predicted_brand_name": COL_BRAND_NAME,
    "predicted_supplier": COL_SUPPLIER,
    "predicted_type": COL_TYPE,
}

REQUIRED_ML_TARGET_COLUMNS = (COL_BRAND_NAME, COL_SUPPLIER, COL_TYPE)

# Prediction export / merge columns (analysis ingests ML app CSV without importing predict code)
MARK_FOR_DELETE_COL = "marked_for_delete"
DELETE_REASON_COL = "delete_reason"

EXPORT_PRESERVE_PREFIX = "_preserve__"


def _norm_key(name: str) -> str:
    return str(name).strip().lower().replace("_", " ")


def find_column(df: pd.DataFrame, canonical: str) -> str | None:
    """Return actual column name in df that maps to canonical, or None."""
    for col in df.columns:
        key = _norm_key(col)
        if key == _norm_key(canonical):
            return col
        if _TARGET_ALIASES.get(key) == canonical:
            return col
    return None


def has_ml_target_columns(df: pd.DataFrame) -> bool:
    """True when BRAND NAME, SUPPLIER, and TYPE exist with at least one non-empty value each."""
    return len(missing_ml_target_names(df)) == 0


def missing_ml_target_names(df: pd.DataFrame) -> list[str]:
    missing: list[str] = []
    for canonical in REQUIRED_ML_TARGET_COLUMNS:
        actual = find_column(df, canonical)
        if actual is None:
            missing.append(canonical)
            continue
        series = df[actual].astype(str).str.strip()
        if series.replace({"", "nan", "NaN", "None", "none"}, pd.NA).dropna().empty:
            missing.append(canonical)
    return missing


def normalize_ml_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """
    Rename legacy / variant headers to BRAND NAME, SUPPLIER, TYPE.
    Matching is by column name only (position ignored).
    """
    out = df.copy()
    rename_map: dict[str, str] = {}
    for col in list(out.columns):
        key = _norm_key(col)
        canonical = _TARGET_ALIASES.get(key) or _PREDICTION_ALIASES.get(key)
        if canonical and col != canonical:
            if canonical not in out.columns and canonical not in rename_map.values():
                rename_map[col] = canonical
    if rename_map:
        out = out.rename(columns=rename_map)
    return out


# Dropped before CSV save/download — recreated automatically when the app loads data.
_STORAGE_DERIVED_COLUMNS = (
    "supplier_raw",       # duplicate of SUPPLIER
    "supplier_group",     # normalized SUPPLIER (rebuilt on load)
    "type_clean",         # duplicate of TYPE
    "material_type",      # normalized TYPE (rebuilt on load)
    "material",           # duplicate of BRAND NAME
    "month_num",          # from month
    "quarter_num",        # from quarter
    "volume_ton",         # volume ÷ 1000 (rebuilt on load)
    "currency_standardized",  # ETL helper; currency kept instead
)


def _normalized_column_key(name: str) -> str:
    return str(name).strip().lower()


def _unwanted_column_keys() -> set[str]:
    from config.settings import UNWANTED_COLS

    return {_normalized_column_key(c) for c in UNWANTED_COLS}


def _column_is_empty(series: pd.Series) -> bool:
    if series.isna().all():
        return True
    text = series.astype(str).str.strip().str.lower()
    return text.replace({"nan": "", "none": ""}, regex=False).eq("").all()


def drop_upload_noise_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Remove ETL-unwanted and all-empty columns before storage/download."""
    if df.empty:
        return df

    unwanted = _unwanted_column_keys()
    drop: list[str] = []
    for col in df.columns:
        key = _normalized_column_key(col)
        if key in unwanted or _column_is_empty(df[col]):
            drop.append(col)
    if not drop:
        return df
    return df.drop(columns=list(dict.fromkeys(drop)), errors="ignore")


def prepare_dataset_for_storage(df: pd.DataFrame) -> pd.DataFrame:
    """Remove internal, duplicate, and predict-only columns before saving CSV."""
    from config.settings import COL_BRAND_NAME, COL_TYPE, PREDICT_CONFIDENCE_COLUMNS
    from services.brand_labels import should_mark_unknown_brand_row

    out = df.copy()
    if MARK_FOR_DELETE_COL in out.columns:
        keep = out[MARK_FOR_DELETE_COL].astype(str).str.strip().str.lower() != "yes"
        out = out.loc[keep].copy()
    brand_col = find_column(out, COL_BRAND_NAME) or (
        COL_BRAND_NAME if COL_BRAND_NAME in out.columns else None
    )
    type_col = find_column(out, COL_TYPE) or (COL_TYPE if COL_TYPE in out.columns else None)
    if brand_col:
        type_series = out[type_col] if type_col else pd.Series([None] * len(out), index=out.index)
        drop_mask = pd.Series(
            [
                should_mark_unknown_brand_row(brand, type_val)
                for brand, type_val in zip(out[brand_col], type_series, strict=False)
            ],
            index=out.index,
        )
        if drop_mask.any():
            out = out.loc[~drop_mask].copy()
    drop: list[str] = []
    for col in out.columns:
        c = str(col)
        if c.startswith("_preserve") or c == "_predict_row_id":
            drop.append(c)
    for col in (*_STORAGE_DERIVED_COLUMNS, MARK_FOR_DELETE_COL, DELETE_REASON_COL, *PREDICT_CONFIDENCE_COLUMNS):
        if col in out.columns:
            drop.append(col)
    out = out.drop(columns=list(dict.fromkeys(drop)), errors="ignore")
    return drop_upload_noise_columns(out)
