"""Shared dataset load, merge, and session state for all analysis tabs."""

from __future__ import annotations



from pathlib import Path



import pandas as pd

import streamlit as st



from config.settings import COL_BRAND_NAME, COL_SUPPLIER, COL_TYPE
from services.analysis_service import prepare_analysis_frame
from services.data_loader_service import load_and_standardize, resolve_ingest_force_etl
from services.data_paths import (
    analysis_dataset_save_path,
    resolve_analysis_dataset,
    temp_file_path,
)

from services.customer_name_service import apply_customer_short_names, find_unmapped_customers
from services.ml_columns import has_ml_target_columns, missing_ml_target_names, prepare_dataset_for_storage



KG_PER_TON = 1000.0





def add_volume_ton(df: pd.DataFrame) -> pd.DataFrame:

    out = df.copy()

    if "volume" in out.columns:

        out["volume_ton"] = pd.to_numeric(out["volume"], errors="coerce") / KG_PER_TON

    else:

        out["volume_ton"] = 0.0

    return out





def ingest_file(source: Path, *, force_etl: bool, hs_codes: list[str] | None = None) -> pd.DataFrame:

    df, _ = load_and_standardize(

        source,

        unit_filter="kg",

        force_etl=force_etl,

        hs_codes=hs_codes if hs_codes is not None else [],

        rows_to_drop=None,

    )

    return apply_customer_short_names(add_volume_ton(prepare_analysis_frame(df)))





def load_default_data(default_dataset: Path, hs_codes: list[str] | None = None) -> pd.DataFrame | None:

    if not default_dataset.exists():

        return None

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

        "supplier_raw",

        "type_clean",

        COL_BRAND_NAME,

        "description",

        "volume_ton",

        "total_usd",

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

        "1. Open **Predict new** in the sidebar (under Model tools).\n"

        "2. Upload the same CSV (raw customs or standardized features are fine).\n"

        "3. Run prediction — the app will fill **BRAND NAME**, **SUPPLIER**, and **TYPE**.\n"

        "4. Download the result, then in Import Analytics choose **Upload new file** "
        "and click **Update data** to merge into your MDI/TDI dataset (same as default file updates)."

    )

    if st.button("Go to Predict new", type="primary", key="goto_predict_from_analysis"):

        st.session_state.nav_page = "predict"

        st.rerun()





def apply_data_source_selection(dataset_mode: str, hs_codes: list[str] | None = None) -> None:

    load_path = resolve_analysis_dataset(dataset_mode)
    save_path = analysis_dataset_save_path(dataset_mode)
    dataset_label = save_path.name

    source_mode = st.session_state.get("dash_source_mode", "Use default file")

    current_source = st.session_state.get("dashboard_source")

    current_df = get_dataframe()



    if source_mode == "Upload new file":

        if current_df is None or current_source != dataset_label:

            base_df = load_default_data(load_path, hs_codes=hs_codes)

            if base_df is not None and has_ml_target_columns(base_df):

                set_dataframe(base_df, dataset_label)

                st.session_state.dashboard_msg = f"Loaded current dataset · {len(base_df):,} rows"

            elif base_df is not None:

                st.session_state.dashboard_df = None

                st.session_state.dashboard_ml_ready = False



        if not st.session_state.get("dash_merge_requested", False):

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

            preview = (

                pd.read_csv(temp, nrows=20, low_memory=False)

                if temp.suffix.lower() == ".csv"

                else pd.read_excel(temp, nrows=20)

            )

            preview.columns = [str(c).strip() for c in preview.columns]

            force_etl = resolve_ingest_force_etl(preview)

            with st.spinner("Processing uploaded file..."):

                incoming_df = ingest_file(temp, force_etl=force_etl, hs_codes=hs_codes)

                incoming_df = prepare_dataset_for_storage(incoming_df)



            if not has_ml_target_columns(incoming_df):

                st.session_state.dashboard_df = None

                st.session_state.dashboard_ml_ready = False

                st.session_state.dash_last_merge_token = upload_token

                render_ml_columns_required_message(incoming_df)

                return



            with st.spinner("Merging with current dataset..."):

                base_df = load_default_data(load_path, hs_codes=hs_codes)

                if base_df is None or not has_ml_target_columns(base_df):

                    base_df = pd.DataFrame()

                merged_df, added_rows, duplicate_rows = append_only_new_rows(base_df, incoming_df)

                save_path.parent.mkdir(parents=True, exist_ok=True)

                prepare_dataset_for_storage(merged_df).to_csv(
                    save_path, index=False, encoding="utf-8-sig"
                )

            set_dataframe(merged_df, dataset_label)

            st.session_state.dash_last_merge_token = upload_token
            unmapped = find_unmapped_customers(merged_df)
            st.session_state.dash_unmapped_customers = unmapped

            st.session_state.dashboard_msg = (
                f"Update complete · Added {added_rows:,} new rows · "
                f"Skipped {duplicate_rows:,} duplicates · "
                f"Total {len(merged_df):,} rows"
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

        if has_ml_target_columns(current_df):

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


