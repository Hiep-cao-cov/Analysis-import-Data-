"""Standardized ML prediction export ingest for sidebar uploads."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from config.settings import MDI_HS_CODES
from services.customer_name_service import apply_customer_short_names
from services.data_loader_service import infer_hs_codes_for_path, is_standardized_dataset, load_file
from services.data_paths import is_seed_dataset_path
from services.ml_columns import prepare_dataset_for_storage
from services.saler_name_service import apply_saler_name_standardization
from services.type_sale_service import apply_type_sale_column, product_line_for_hs_codes

STANDARDIZED_UPLOAD_HINT = (
    "Upload must be an ML prediction export with the same columns as "
    "data/predictions_pmdi_etl.csv (hs_code, description, BRAND NAME, SUPPLIER, TYPE, …)."
)


def classify_upload_format(preview: pd.DataFrame) -> str:
    if is_standardized_dataset(preview):
        return "ML prediction export"
    return "Unsupported format"


def _resolve_hs_codes(source: Path, hs_codes: list[str] | None) -> list[str]:
    if hs_codes:
        return hs_codes
    inferred = infer_hs_codes_for_path(source)
    return inferred if inferred is not None else MDI_HS_CODES


def ingest_upload_file(
    source: Path,
    *,
    hs_codes: list[str] | None = None,
) -> pd.DataFrame:
    """
    Load a standardized ML prediction CSV for merge / dashboard preview.

    Rows with marked_for_delete=Yes are removed in prepare_dataset_for_storage.
    """
    path = Path(source)
    header = load_file(path)
    if not is_standardized_dataset(header):
        raise ValueError(STANDARDIZED_UPLOAD_HINT)

    codes = _resolve_hs_codes(path, hs_codes)
    from services.data_loader_service import load_and_standardize

    df, _ = load_and_standardize(
        path,
        unit_filter="kg",
        force_etl=False,
        hs_codes=codes,
    )
    return prepare_dataset_for_storage(df)


def load_storage_dataset(
    source: Path,
    *,
    hs_codes: list[str] | None = None,
) -> pd.DataFrame:
    """
    Load saved/seed CSV for merge duplicate check (storage columns, no chart derivatives).
    Seed files get in-memory customer / saler / type_sale enrichment without ETL.
    """
    path = Path(source)
    if not path.is_file():
        return pd.DataFrame()

    df = load_file(path)
    product_line = product_line_for_hs_codes(hs_codes, path=path)

    if is_seed_dataset_path(path):
        df = apply_customer_short_names(df)
        df = apply_saler_name_standardization(df)
        df = apply_type_sale_column(df, product_line=product_line)
    elif "saler" in df.columns:
        df = apply_customer_short_names(df)
        df = apply_saler_name_standardization(df)
        df = apply_type_sale_column(df, product_line=product_line)

    return prepare_dataset_for_storage(df)
