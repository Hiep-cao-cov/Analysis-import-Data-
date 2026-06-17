"""Full ETL ingest for sidebar uploads (predictions_* / raw customs → analysis storage schema)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from config.settings import MDI_HS_CODES
from services.customer_name_service import apply_customer_short_names
from services.data_loader_service import (
    infer_hs_codes_for_path,
    is_prediction_upload_format,
    is_raw_customs_export,
    is_standardized_dataset,
    load_file,
    run_upload_etl,
)
from services.data_paths import is_seed_dataset_path
from services.ml_columns import prepare_dataset_for_storage
from services.saler_name_service import apply_saler_name_standardization
from services.type_sale_service import apply_type_sale_column, product_line_for_hs_codes


def upload_requires_full_etl(preview: pd.DataFrame) -> bool:
    """
    True when upload must run full ETL (OrderDataPipeline + run_etl).

    Covers predictions_pmdi_* style (Vietnamese columns + BRAND NAME / SUPPLIER / TYPE)
    and plain raw customs exports.
    """
    if is_prediction_upload_format(preview):
        return True
    if is_raw_customs_export(preview):
        return True
    return False


def classify_upload_format(preview: pd.DataFrame) -> str:
    if is_prediction_upload_format(preview):
        return "Prediction upload (full ETL)"
    if is_standardized_dataset(preview):
        return "Standardized dataset"
    if is_raw_customs_export(preview):
        return "Raw customs (full ETL)"
    return "Unrecognized format"


def _resolve_hs_codes(source: Path, hs_codes: list[str] | None) -> list[str]:
    if hs_codes:
        return hs_codes
    inferred = infer_hs_codes_for_path(source)
    return inferred if inferred is not None else MDI_HS_CODES


def ingest_upload_file(
    source: Path,
    *,
    hs_codes: list[str] | None = None,
    apply_description_blacklist: bool = False,
) -> pd.DataFrame:
    """
    Process an uploaded file for merge:

    1. Full ETL when predictions_* / raw customs (column rename, ton→kg, USD price,
       month/quarter, Sale_chanel, customer short names, saler, type_sale DIRECT/INDIRECT)
    2. Light path only for already-English standardized CSVs
    3. prepare_dataset_for_storage — ready to save / merge / ML gate
    """
    path = Path(source)
    header = load_file(path)
    codes = _resolve_hs_codes(path, hs_codes)

    if upload_requires_full_etl(header):
        df = run_upload_etl(
            path,
            hs_codes=codes,
            apply_description_blacklist=apply_description_blacklist,
        )
    else:
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
