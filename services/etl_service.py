"""ETL service: raw customs CSV → standardized analysis-ready dataset."""
from pathlib import Path

import pandas as pd

from config.settings import (
    ALLOWED_UNITS,
    COLUMN_RENAME_MAP,
    MDI_HS_CODES,
    TDI_HS_CODES,
    UNWANTED_COLS,
)
from services.data_process import (
    OrderDataPipeline,
    filter_by_hs_code,
    parse_string_to_float,
    rename_dataframe_columns,
)
from services.description_blacklist import get_description_blacklist_terms
from services.ml_columns import normalize_ml_column_names
from services.customer_name_service import apply_customer_short_names
from services.sale_channel_service import add_sale_channel_column


def _product_line_for_hs_codes(hs_codes: list[str] | None) -> str | None:
    if hs_codes is None:
        return None
    if set(hs_codes) == set(MDI_HS_CODES):
        return "MDI"
    if set(hs_codes) == set(TDI_HS_CODES):
        return "TDI"
    return None


def build_pipeline(*, hs_codes: list[str] | None = None) -> OrderDataPipeline:
    product_line = _product_line_for_hs_codes(hs_codes)
    blacklist_terms = get_description_blacklist_terms(product_line=product_line)
    return OrderDataPipeline(
        cols_to_drop=UNWANTED_COLS,
        target_units=ALLOWED_UNITS,
        numeric_parser=parse_string_to_float,
        default_decimals=3,
        blacklist_terms=blacklist_terms,
        product_line=product_line,
    )


def run_etl(
    raw_path: str | Path,
    *,
    hs_codes: list[str] | None = None,
    unit_filter: str = "kg",
    save_path: str | Path | None = None,
    rows_to_drop: str | None = None,
) -> pd.DataFrame:
    """
    Full ETL: load raw file → pipeline → HS filter → rename → optional unit filter.
    """
    _ = rows_to_drop  # deprecated — blacklist terms are in config/settings.py
    hs_codes = MDI_HS_CODES if hs_codes is None else hs_codes
    pipeline = build_pipeline(hs_codes=hs_codes)
    df = pipeline.run(str(raw_path))
    if hs_codes:
        df = filter_by_hs_code(df, hs_codes)
    df = rename_dataframe_columns(df, COLUMN_RENAME_MAP)
    df = add_sale_channel_column(df)

    if unit_filter:
        df = df[df["unit"] == unit_filter].copy()

    df = normalize_ml_column_names(df)
    df = apply_customer_short_names(df)
    df = df.reset_index(drop=True)

    if save_path:
        out = Path(save_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(out, index=False, encoding="utf-8-sig")

    return df
