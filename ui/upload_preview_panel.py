"""Sidebar upload preview — validation and dry-run merge stats."""
from __future__ import annotations

import io

import pandas as pd
import streamlit as st

from config.settings import ANALYSIS_HS_CODE_OPTIONS, COL_BRAND_NAME, COL_SUPPLIER, COL_TYPE
from services.upload_preview import UploadPreviewResult, build_upload_preview
from ui.analysis_data import (
    append_only_new_rows,
    get_dataframe,
    prepare_dataframe_for_analysis,
    set_dataframe,
    upload_preview_source_name,
)
from services.upload_ingest_service import ingest_upload_file, load_storage_dataset
from services.data_paths import temp_file_path


_PREVIEW_CACHE_KEY = "dash_upload_preview_cache"
_UPLOAD_PREVIEW_TOKEN_KEY = "dash_upload_preview_token"
_UPLOAD_DATASET_MODE_KEY = "dash_upload_dataset_mode"


def _normalize_dataset_mode(mode: str) -> str:
    m = str(mode).strip().upper()
    return "MDI" if m == "PMDI" else m


def _upload_token(uploaded) -> str:
    return f"{uploaded.name}:{len(uploaded.getvalue())}"


def get_upload_preview(uploaded) -> UploadPreviewResult | None:
    if uploaded is None:
        return None

    mode = _normalize_dataset_mode(st.session_state.get("analysis_mode", "MDI"))
    token = f"{_upload_token(uploaded)}|{mode}"
    cached = st.session_state.get(_PREVIEW_CACHE_KEY)
    if isinstance(cached, dict) and cached.get("token") == token:
        data = cached["result"]
        if isinstance(data, UploadPreviewResult):
            return data

    hs_codes = ANALYSIS_HS_CODE_OPTIONS.get(mode, ANALYSIS_HS_CODE_OPTIONS["MDI"])
    last_merge = st.session_state.get("dash_last_merge_token")

    temp = temp_file_path("preview", uploaded.name)
    with st.spinner("Checking upload…"):
        result = build_upload_preview(
            file_name=uploaded.name,
            file_bytes=uploaded.getvalue(),
            temp_path=temp,
            dataset_mode=mode,
            hs_codes=hs_codes,
            last_merge_token=last_merge,
            ingest_file_fn=ingest_upload_file,
            load_default_data_fn=load_storage_dataset,
            append_only_new_rows_fn=append_only_new_rows,
        )

    st.session_state[_PREVIEW_CACHE_KEY] = {"token": token, "result": result}
    return result


def clear_upload_preview_cache() -> None:
    st.session_state.pop(_PREVIEW_CACHE_KEY, None)
    st.session_state.pop(_UPLOAD_PREVIEW_TOKEN_KEY, None)
    st.session_state.pop(_UPLOAD_DATASET_MODE_KEY, None)


def clear_sidebar_upload_state(*, reset_source_mode: bool = True) -> None:
    """
    Drop upload file + preview when MDI/TDI dataset changes.
    Resets data source to default so the new dataset's seed file loads.
    """
    clear_upload_preview_cache()
    st.session_state.pop("dash_sidebar_upload", None)
    st.session_state.pop("dash_last_merge_token", None)
    st.session_state.dash_merge_requested = False
    if reset_source_mode:
        st.session_state.dash_source_mode = "Use default file"


def ensure_upload_preview_dashboard(uploaded, *, hs_codes: list[str] | None) -> bool:
    """
    After full ETL, load upload-only rows into dashboard_df so tabs work immediately
    (same chart logic as default file, without merging into saved dataset).
    """
    if uploaded is None:
        return False

    preview = get_upload_preview(uploaded)
    if preview is None or preview.error or preview.already_merged or preview.dataset_mismatch:
        if preview is not None and preview.error:
            st.session_state.dashboard_df = None
            st.session_state.dashboard_ml_ready = False
            st.session_state.pop(_UPLOAD_DATASET_MODE_KEY, None)
        return False

    if not preview.ml_ready or not preview.processed_csv:
        st.session_state.dashboard_df = None
        st.session_state.dashboard_ml_ready = False
        return False

    token = _upload_token(uploaded)
    source_name = upload_preview_source_name(uploaded.name)
    mode = _normalize_dataset_mode(st.session_state.get("analysis_mode", "MDI"))
    if (
        st.session_state.get("dashboard_source") == source_name
        and st.session_state.get(_UPLOAD_PREVIEW_TOKEN_KEY) == token
        and st.session_state.get(_UPLOAD_DATASET_MODE_KEY) == mode
        and get_dataframe() is not None
    ):
        hs = hs_codes or ANALYSIS_HS_CODE_OPTIONS.get(mode, ANALYSIS_HS_CODE_OPTIONS["MDI"])
        refreshed = prepare_dataframe_for_analysis(get_dataframe(), hs_codes=hs)
        set_dataframe(refreshed, source_name)
        st.session_state.dashboard_ml_ready = True
        return True

    storage_df = pd.read_csv(
        io.BytesIO(preview.processed_csv),
        encoding="utf-8-sig",
        low_memory=False,
    )
    hs = hs_codes or ANALYSIS_HS_CODE_OPTIONS.get(mode, ANALYSIS_HS_CODE_OPTIONS["MDI"])
    df = prepare_dataframe_for_analysis(storage_df, hs_codes=hs)
    set_dataframe(df, source_name)
    st.session_state[_UPLOAD_PREVIEW_TOKEN_KEY] = token
    st.session_state[_UPLOAD_DATASET_MODE_KEY] = mode
    st.session_state.dashboard_msg = (
        f"Upload preview · {len(df):,} rows — dashboards show **this file only**. "
        f"Click **Update data** to merge into the saved dataset."
    )
    return True


def render_upload_preview_panel(uploaded) -> bool:
    """
    Show upload validation and dry-run merge estimate.
    Returns True when Update data should be enabled.
    """
    if uploaded is None:
        st.caption("Select a CSV or Excel file to see a validation preview.")
        return False

    preview = get_upload_preview(uploaded)
    if preview is None:
        return False

    st.markdown("**Upload preview**")

    if preview.error:
        st.error(preview.error)
        return False

    if preview.dataset_mismatch:
        return False

    if preview.already_merged:
        st.info("This file was already merged. Upload a different file or change the file to update again.")
        return False

    if preview.ml_ready:
        st.success("Ready for analytics — BRAND NAME, SUPPLIER, TYPE present.")
        st.caption("Dashboards below use **upload data only** until you click Update data.")
    else:
        missing = ", ".join(preview.missing_ml_columns) or f"{COL_BRAND_NAME}, {COL_SUPPLIER}, {COL_TYPE}"
        st.error(f"Missing or empty: **{missing}**")
        st.caption("Run the ML Predict app first, then upload the prediction CSV.")

    st.markdown(f"- **File type:** {preview.file_kind}")
    st.markdown(f"- **Rows in upload:** {preview.row_count:,}")
    if preview.upload_coverage:
        st.markdown(f"- **Upload period:** {preview.upload_coverage}")

    if preview.base_row_count:
        st.markdown(f"- **Current saved dataset:** {preview.base_row_count:,} rows")
        if preview.base_coverage:
            st.markdown(f"- **Current period:** {preview.base_coverage}")

    if preview.ml_ready:
        st.markdown(
            f"- **Dry-run merge:** +{preview.new_rows:,} new · "
            f"{preview.duplicate_rows:,} duplicates skipped · "
            f"{preview.total_after_merge:,} total after merge"
        )
        if preview.new_rows == 0 and preview.row_count > 0:
            st.warning("All upload rows look like duplicates — nothing new would be added.")

    for warning in preview.warnings:
        st.caption(f"⚠ {warning}")

    if preview.sample is not None and not preview.sample.empty:
        with st.expander("Sample rows (first 5)", expanded=False):
            st.dataframe(preview.sample, use_container_width=True, hide_index=True)

    if preview.processed_csv and preview.processed_download_name:
        st.caption(
            "Download the ETL output (renamed columns, kg, short names, saler, month/quarter, "
            "type_sale, Sale_chanel) and review before merging."
        )
        st.download_button(
            "Download processed file",
            data=preview.processed_csv,
            file_name=preview.processed_download_name,
            mime="text/csv",
            use_container_width=True,
            key="dash_download_processed_upload",
            disabled=preview.already_merged,
            help="Same file that Update data would merge — does not change your dataset.",
        )

    return preview.ready_for_merge
