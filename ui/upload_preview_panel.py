"""Sidebar upload preview — validation and dry-run merge stats."""
from __future__ import annotations

import streamlit as st

from config.settings import ANALYSIS_HS_CODE_OPTIONS, COL_BRAND_NAME, COL_SUPPLIER, COL_TYPE
from services.upload_preview import UploadPreviewResult, build_upload_preview
from ui.analysis_data import (
    append_only_new_rows,
    ingest_file,
    load_default_data,
    prepare_dataset_for_storage,
)
from services.data_paths import temp_file_path


_PREVIEW_CACHE_KEY = "dash_upload_preview_cache"


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
            ingest_file_fn=ingest_file,
            load_default_data_fn=load_default_data,
            append_only_new_rows_fn=append_only_new_rows,
            prepare_dataset_for_storage_fn=prepare_dataset_for_storage,
        )

    st.session_state[_PREVIEW_CACHE_KEY] = {"token": token, "result": result}
    return result


def clear_upload_preview_cache() -> None:
    st.session_state.pop(_PREVIEW_CACHE_KEY, None)


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
        st.error(f"Could not read file: {preview.error}")
        return False

    if preview.already_merged:
        st.info("This file was already merged. Upload a different file or change the file to update again.")
        return False

    if preview.ml_ready:
        st.success("Ready for analytics — BRAND NAME, SUPPLIER, TYPE present.")
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

    return preview.ready_for_merge
