"""Shared dataset load, merge, and session state for all analysis tabs."""

from __future__ import annotations



from pathlib import Path



import pandas as pd

import streamlit as st



from config.settings import COL_BRAND_NAME, COL_SUPPLIER, COL_TYPE
from services.analysis_service import prepare_analysis_frame
from services.data_loader_service import load_and_standardize, load_file
from services.upload_ingest_service import ingest_upload_file, load_storage_dataset
from services.data_paths import (
    analysis_dataset_save_path,
    is_seed_dataset_path,
    resolve_analysis_dataset,
    temp_file_path,
)
from services.customer_name_service import apply_customer_short_names, find_unmapped_customers
from services.saler_name_service import apply_saler_name_standardization
from services.type_sale_service import apply_type_sale_column, product_line_for_hs_codes

from services.ml_columns import has_ml_target_columns, missing_ml_target_names, prepare_dataset_for_storage



KG_PER_TON = 1000.0

UPLOAD_PREVIEW_SOURCE_PREFIX = "upload_preview:"





def add_volume_ton(df: pd.DataFrame) -> pd.DataFrame:

    out = df.copy()

    if "volume" in out.columns:

        out["volume_ton"] = pd.to_numeric(out["volume"], errors="coerce") / KG_PER_TON

    else:

        out["volume_ton"] = 0.0

    return out





def load_seed_dataset_for_analysis(
    source: Path,
    hs_codes: list[str] | None = None,
) -> pd.DataFrame:
    """
    Load app_data seed CSV without ETL or row filters.
    Applies customer short names + saler/type_sale in memory; seed file on disk is not modified.
    """
    df = load_file(source)
    product_line = product_line_for_hs_codes(hs_codes, path=source)
    df = apply_customer_short_names(df)
    df = apply_saler_name_standardization(df)
    df = apply_type_sale_column(df, product_line=product_line)
    return prepare_dataframe_for_analysis(df, hs_codes=hs_codes, path=source)


def prepare_dataframe_for_analysis(
    df: pd.DataFrame,
    *,
    hs_codes: list[str] | None = None,
    path: Path | None = None,
) -> pd.DataFrame:
    """Add chart/filter columns for dashboard_df; always re-apply saler rules in memory."""
    if df.empty:
        return df
    product_line = product_line_for_hs_codes(hs_codes, path=path)
    df = apply_saler_name_standardization(df)
    df = apply_type_sale_column(df, product_line=product_line)
    return add_volume_ton(prepare_analysis_frame(df))


def is_upload_preview_source(source_name: str | None) -> bool:
    return str(source_name or "").startswith(UPLOAD_PREVIEW_SOURCE_PREFIX)


def upload_preview_source_name(file_name: str) -> str:
    return f"{UPLOAD_PREVIEW_SOURCE_PREFIX}{file_name}"


def ingest_file(source: Path, *, force_etl: bool, hs_codes: list[str] | None = None) -> pd.DataFrame:
    """Load merged dataset under data/ for analysis (light path + analysis columns)."""
    df, _ = load_and_standardize(
        source,
        unit_filter="kg",
        force_etl=force_etl,
        hs_codes=hs_codes if hs_codes is not None else [],
        rows_to_drop=None,
    )
    return prepare_dataframe_for_analysis(df, hs_codes=hs_codes, path=source)


def load_default_data(default_dataset: Path, hs_codes: list[str] | None = None) -> pd.DataFrame | None:
    if not default_dataset.exists():
        return None
    if is_seed_dataset_path(default_dataset):
        return load_seed_dataset_for_analysis(default_dataset, hs_codes=hs_codes)
    return ingest_file(default_dataset, force_etl=False, hs_codes=hs_codes)





def get_dataframe() -> pd.DataFrame | None:

    return st.session_state.get("dashboard_df")





def set_dataframe(df: pd.DataFrame, source_name: str) -> None:

    st.session_state.dashboard_df = df

    st.session_state.dashboard_source = source_name

    st.session_state.dashboard_ml_ready = has_ml_target_columns(df)





def build_row_signature(df: pd.DataFrame, key_cols: list[str]) -> pd.Series:

    norm = pd.DataFrame(index=df.index)

    for c in key_cols:

        s = df[c] if c in df.columns else pd.Series("", index=df.index)

        if c == "date":

            s = pd.to_datetime(s, errors="coerce").dt.strftime("%Y-%m-%d")

        elif c in {"volume_ton", "volume", "total_usd", "unit_price"}:

            s = pd.to_numeric(s, errors="coerce").round(6)

        norm[c] = s.fillna("").astype(str).str.strip().str.lower()

    return pd.util.hash_pandas_object(norm, index=False).astype(str)





def append_only_new_rows(base_df: pd.DataFrame, incoming_df: pd.DataFrame) -> tuple[pd.DataFrame, int, int]:

    key_priority = [

        "date",

        "hs_code",

        "customer_id",

        "customer_name",

        COL_SUPPLIER,

        COL_TYPE,

        COL_BRAND_NAME,

        "saler",

        "description",

        "volume",

        "volume_ton",

        "total_usd",

        "transaction",

        "supplier_raw",

        "type_clean",

    ]

    key_cols = [c for c in key_priority if c in base_df.columns and c in incoming_df.columns]

    if not key_cols:

        key_cols = sorted(set(base_df.columns).intersection(incoming_df.columns))

    if not key_cols:

        merged = pd.concat([base_df, incoming_df], ignore_index=True, sort=False)

        return merged, len(incoming_df), 0



    base_sig = build_row_signature(base_df, key_cols)

    incoming_sig = build_row_signature(incoming_df, key_cols)

    is_new_mask = ~incoming_sig.isin(set(base_sig))

    new_rows = incoming_df[is_new_mask].copy()

    dup_count = int((~is_new_mask).sum())

    merged = pd.concat([base_df, new_rows], ignore_index=True, sort=False)

    return merged, int(len(new_rows)), dup_count





def render_ml_columns_required_message(df: pd.DataFrame | None = None) -> None:

    """Explain missing BRAND NAME / SUPPLIER / TYPE and how to run prediction."""

    missing = missing_ml_target_names(df) if df is not None else list(

        (COL_BRAND_NAME, COL_SUPPLIER, COL_TYPE)

    )

    st.error(

        "This dataset cannot be used for Import Analytics until it includes "

        f"**{COL_BRAND_NAME}**, **{COL_SUPPLIER}**, and **{COL_TYPE}** "

        "(column names only — position does not matter)."

    )

    if missing:

        st.markdown(f"Missing or empty: **{', '.join(missing)}**.")

    st.markdown(

        "1. Open the **MDI Train & Predict** app (`ml_app/`) on raw or partial customs data.\n"

        "2. Run prediction — it fills **BRAND NAME**, **SUPPLIER**, and **TYPE**.\n"

        "3. Download the CSV, then here choose **Upload new file → Update data** to merge."

    )

    st.info(
        "Data Analysis and Train/Predict are separate apps. "
        "Upload the prediction CSV from the ML app — no link between the two processes."
    )





def apply_data_source_selection(dataset_mode: str, hs_codes: list[str] | None = None) -> None:

    load_path = resolve_analysis_dataset(dataset_mode)
    save_path = analysis_dataset_save_path(dataset_mode)
    dataset_label = save_path.name

    source_mode = st.session_state.get("dash_source_mode", "Use default file")

    current_source = st.session_state.get("dashboard_source")

    current_df = get_dataframe()



    if source_mode == "Upload new file":

        uploaded = st.session_state.get("dash_sidebar_upload")
        upload_dataset_mode = st.session_state.get("dash_upload_dataset_mode")
        current_mode = str(dataset_mode).strip().upper()
        if current_mode == "PMDI":
            current_mode = "MDI"

        if (
            upload_dataset_mode
            and str(upload_dataset_mode).upper() != current_mode
            and is_upload_preview_source(current_source)
        ):
            st.session_state.dashboard_df = None
            st.session_state.dashboard_source = None
            st.session_state.dashboard_ml_ready = False
            st.session_state.dashboard_msg = None

        if not st.session_state.get("dash_merge_requested", False):
            from ui.upload_preview_panel import ensure_upload_preview_dashboard

            if uploaded is not None:
                ensure_upload_preview_dashboard(uploaded, hs_codes=hs_codes)
            else:
                st.session_state.dashboard_df = None
                st.session_state.dashboard_ml_ready = False
                st.session_state.dashboard_msg = None
            return

        st.session_state.dash_merge_requested = False



        uploaded = st.session_state.get("dash_sidebar_upload")

        if uploaded is None:

            st.warning("Please upload a file before clicking Update data.")

            return

        upload_token = f"{uploaded.name}:{len(uploaded.getvalue())}"

        if st.session_state.get("dash_last_merge_token") == upload_token:

            st.info("This file was already processed. Upload a new file or modify the file to update again.")

            return

        try:

            temp = temp_file_path("upload", uploaded.name)

            temp.write_bytes(uploaded.getvalue())

            with st.spinner("Processing uploaded file (full ETL)..."):

                incoming_df = ingest_upload_file(temp, hs_codes=hs_codes)



            if not has_ml_target_columns(incoming_df):

                st.session_state.dashboard_df = None

                st.session_state.dashboard_ml_ready = False

                st.session_state.dash_last_merge_token = upload_token

                render_ml_columns_required_message(incoming_df)

                return



            with st.spinner("Merging with current dataset..."):

                base_df = load_storage_dataset(load_path, hs_codes=hs_codes)

                if base_df is None or base_df.empty or not has_ml_target_columns(base_df):

                    base_df = pd.DataFrame()

                merged_storage, added_rows, duplicate_rows = append_only_new_rows(base_df, incoming_df)

                save_path.parent.mkdir(parents=True, exist_ok=True)

                prepare_dataset_for_storage(merged_storage).to_csv(
                    save_path, index=False, encoding="utf-8-sig"
                )

            merged_df = prepare_dataframe_for_analysis(
                merged_storage, hs_codes=hs_codes, path=load_path
            )
            set_dataframe(merged_df, dataset_label)

            st.session_state.dash_last_merge_token = upload_token
            from ui.upload_preview_panel import clear_upload_preview_cache

            clear_upload_preview_cache()
            st.session_state.pop("dash_upload_preview_token", None)
            unmapped = find_unmapped_customers(merged_storage)
            st.session_state.dash_unmapped_customers = unmapped

            st.session_state.dashboard_msg = (
                f"Update complete · Added {added_rows:,} new rows · "
                f"Skipped {duplicate_rows:,} duplicates · "
                f"Total {len(merged_storage):,} rows"
            )
            if not unmapped.empty:
                st.session_state.dashboard_msg += (
                    f" · **{len(unmapped):,} new customer(s)** not in customer_list.csv "
                    f"(see **Customer short names** in sidebar)"
                )

        except Exception as e:

            st.error(f"Update failed: {e}")

        return



    if current_df is not None and current_source == dataset_label:
        refreshed = prepare_dataframe_for_analysis(
            current_df, hs_codes=hs_codes, path=load_path
        )
        set_dataframe(refreshed, dataset_label)
        if has_ml_target_columns(refreshed):
            st.session_state.dashboard_ml_ready = True
        return

    try:

        df = load_default_data(load_path, hs_codes=hs_codes)

        if df is None:

            return

        if has_ml_target_columns(df):

            set_dataframe(df, dataset_label)

            st.session_state.dashboard_msg = f"Loaded default file · {len(df):,} rows"

        else:

            st.session_state.dashboard_df = None

            st.session_state.dashboard_ml_ready = False

            st.session_state.dashboard_msg = None

    except Exception as e:

        st.error(f"Could not load default file: {e}")


