"""Canonical ML / analytics column names (name-based, not position)."""
from __future__ import annotations

import pandas as pd

from config.settings import COL_BRAND_NAME, COL_SUPPLIER, COL_TYPE, COLUMN_RENAME_MAP

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

# Keep ETL-standardized values in prediction export (do not restore pre-ETL snapshots).
EXPORT_PRESERVE_SKIP_COLUMNS = frozenset({
    "unit",
    "unit_price",
    "volume",
    "customer_name",
})


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


def apply_predictions_to_targets(df: pd.DataFrame) -> pd.DataFrame:
    """Map predicted_* columns into BRAND NAME / SUPPLIER / TYPE."""
    out = normalize_ml_column_names(df.copy())
    legacy_preds = {
        "predicted_label": COL_BRAND_NAME,
        "predicted_supplier": COL_SUPPLIER,
        "predicted_type": COL_TYPE,
    }
    for pred_col, canonical in legacy_preds.items():
        if pred_col not in out.columns:
            continue
        if canonical not in out.columns:
            out[canonical] = out[pred_col]
        else:
            mask = out[canonical].isna() | (
                out[canonical].astype(str).str.strip().isin(["", "nan", "NaN", "None"])
            )
            out.loc[mask, canonical] = out.loc[mask, pred_col]
        out = out.drop(columns=[pred_col], errors="ignore")
    return out


def restore_preserved_text_columns(
    df: pd.DataFrame,
    *,
    keep_predict_row_id: bool = False,
) -> pd.DataFrame:
    """Restore original input values for export after ETL mutations."""
    return restore_all_preserved_export_columns(
        df,
        keep_predict_row_id=keep_predict_row_id,
    )


def restore_all_preserved_export_columns(
    df: pd.DataFrame,
    *,
    keep_predict_row_id: bool = False,
) -> pd.DataFrame:
    """Replace ETL-mutated columns with pre-ETL snapshots (original casing/format)."""
    out = df.copy()
    rename_map = {str(k).strip().lower(): str(v).strip() for k, v in COLUMN_RENAME_MAP.items()}

    for col in list(out.columns):
        col_str = str(col)
        if not col_str.startswith(EXPORT_PRESERVE_PREFIX):
            continue
        old_col = col_str[len(EXPORT_PRESERVE_PREFIX) :]
        target = rename_map.get(old_col, old_col)
        if target in EXPORT_PRESERVE_SKIP_COLUMNS:
            out = out.drop(columns=[col_str])
            continue
        if target in out.columns:
            out[target] = out[col]
        out = out.drop(columns=[col_str])

    if not keep_predict_row_id:
        out = out.drop(columns=["_predict_row_id"], errors="ignore")
    return finalize_export_unit_columns(out)


def finalize_export_unit_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure export uses kg-only labels after tấn→kg ETL conversion."""
    out = df.copy()
    if "unit" not in out.columns:
        return out
    normalized = out["unit"].astype(str).str.strip().str.lower()
    kg_like = {"kg", "kgs", "kilogram", "kilograms"}
    ton_like = {"tấn", "tan", "ton", "tons"}
    out["unit"] = normalized.map(
        lambda u: "kg" if u in kg_like or u in ton_like else u
    )
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
    return out.drop(columns=list(dict.fromkeys(drop)), errors="ignore")
