"""Load raw or standardized files; run ETL when needed."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from config.settings import DATA_DIR, MDI_HS_CODES, ML_COLUMN_CONFIG
from services.etl_service import run_etl
from services.customer_name_service import apply_customer_short_names
from services.saler_name_service import apply_saler_name_standardization
from services.type_sale_service import apply_type_sale_column, product_line_for_hs_codes
from services.ml_columns import normalize_ml_column_names
from services.sale_channel_service import add_sale_channel_column

_ML_FEATURE_COLUMNS = (
    ML_COLUMN_CONFIG["hs_code"],
    ML_COLUMN_CONFIG["product_description"],
    ML_COLUMN_CONFIG["saler"],
    ML_COLUMN_CONFIG["country_origin"],
)

STANDARDIZED_MARKERS = {"hs_code", "description", "customer_id", "total_usd"}
RAW_MARKERS = {"hs code", "chung loai hang hoa xuat nhap", "ma doanh nghiep", "tri gia usd"}


def _normalize_columns(df: pd.DataFrame) -> set[str]:
    return {str(c).strip().lower() for c in df.columns}


def is_raw_customs_export(df: pd.DataFrame) -> bool:
    cols = _normalize_columns(df)
    return bool(cols & RAW_MARKERS) and "hs_code" not in cols


def is_standardized_dataset(df: pd.DataFrame) -> bool:
    cols = _normalize_columns(df)
    return len(cols & STANDARDIZED_MARKERS) >= 3


def is_prediction_export(df: pd.DataFrame) -> bool:
    """
    True for CSV/Excel saved from Predict new (or equivalent): filled
    BRAND NAME / SUPPLIER / TYPE plus standardized import columns.
    """
    from services.ml_columns import has_ml_target_columns, normalize_ml_column_names

    out = normalize_ml_column_names(df)
    if not has_ml_target_columns(out):
        return False
    cols = _normalize_columns(out)
    return "hs_code" in cols or len(cols & STANDARDIZED_MARKERS) >= 3


def resolve_ingest_force_etl(preview: pd.DataFrame) -> bool:
    """Skip full ETL when upload is already a prediction export or standardized dataset."""
    if is_prediction_export(preview) or is_standardized_dataset(preview):
        return False
    return is_raw_customs_export(preview)


def has_ml_feature_columns(df: pd.DataFrame) -> bool:
    """True when hs_code, description, saler, country_origin exist (ETL output names)."""
    return all(col in df.columns for col in _ML_FEATURE_COLUMNS)


def infer_hs_codes_for_path(path: Path) -> list[str] | None:
    """Pick HS filter from filename (PMDI vs TDI); None → ETL default (MDI)."""
    from config.settings import TDI_HS_CODES

    name = path.name.lower()
    if "tdi" in name:
        return TDI_HS_CODES
    if "pmdi" in name or "mdi" in name:
        return MDI_HS_CODES
    return None


def load_for_ml(
    source: Path | str,
    *,
    unit_filter: str = "kg",
    hs_codes: list[str] | None = None,
) -> pd.DataFrame:
    """
    Load a training/inference file: run ETL when raw or missing feature columns,
    then normalize BRAND NAME / SUPPLIER / TYPE headers.
    """
    path = Path(source)
    df = load_file(path)
    hs_codes = infer_hs_codes_for_path(path) if hs_codes is None else hs_codes

    if is_raw_customs_export(df) or not has_ml_feature_columns(df):
        df, _ = load_and_standardize(
            path,
            unit_filter=unit_filter,
            force_etl=True,
            hs_codes=hs_codes,
        )
    return apply_customer_short_names(normalize_ml_column_names(df))


def load_file(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        df = pd.read_csv(path, low_memory=False)
    elif suffix in (".xlsx", ".xls"):
        df = pd.read_excel(path)
    else:
        raise ValueError(f"Unsupported file type: {suffix}")

    # Normalize header names once at ingestion time so:
    # - column position never matters (name-based access only),
    # - accidental leading/trailing spaces in headers don't break mapping.
    df.columns = [str(c).strip() for c in df.columns]
    return normalize_ml_column_names(df)


def load_and_standardize(
    source: Path,
    *,
    unit_filter: str = "kg",
    save_path: Path | None = None,
    force_etl: bool = False,
    hs_codes: list[str] | None = None,
    rows_to_drop: str | None = None,
) -> tuple[pd.DataFrame, str]:
    """
    Load CSV/Excel. Run ETL if raw customs export; otherwise use as-is.
    Returns (dataframe, status_message).
    """
    df = load_file(source)

    if force_etl or is_raw_customs_export(df):
        df = run_etl(
            source,
            hs_codes=hs_codes,
            unit_filter=unit_filter or None,
            save_path=save_path,
            rows_to_drop=rows_to_drop,
        )
        msg = f"ETL applied · {len(df):,} rows standardized"
        if save_path:
            msg += f" · saved to {save_path.name}"
        return df, msg

    if unit_filter and "unit" in df.columns:
        df = df[df["unit"].astype(str).str.lower() == unit_filter.lower()].copy()

    df = add_sale_channel_column(df)
    df = apply_customer_short_names(df)
    df = apply_saler_name_standardization(df)
    df = apply_type_sale_column(
        df, product_line=product_line_for_hs_codes(hs_codes, path=source)
    )
    df = df.reset_index(drop=True)
    msg = f"Loaded standardized dataset · {len(df):,} rows"
    if save_path:
        save_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(save_path, index=False, encoding="utf-8-sig")
        msg += f" · saved to {save_path.name}"
    return df, msg
