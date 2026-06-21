"""Sidebar upload preview — validation and dry-run merge stats."""
from __future__ import annotations

import streamlit as st

from config.settings import ANALYSIS_HS_CODE_OPTIONS, COL_BRAND_NAME, COL_SUPPLIER, COL_TYPE
from services.upload_preview import UploadPreviewResult, build_upload_preview
from ui.analysis_data import (
    append_only_new_rows,
    finish_dashboard_load,
    get_dataframe,
    load_upload_for_dashboard,
    upload_preview_source_name,
)
from services.upload_ingest_service import ingest_upload_file, load_storage_dataset
from services.data_paths import temp_file_path


_PREVIEW_CACHE_KEY = "dash_upload_preview_cache"
_UPLOAD_PREVIEW_TOKEN_KEY = "dash_upload_preview_token"
_UPLOAD_DATASET_MODE_KEY = "dash_upload_dataset_mode"
_UPLOAD_FILE_TOKEN_KEY = "dash_upload_file_token"


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
            ingest_file_fn=lambda path, hs_codes=None: ingest_upload_file(
                path,
                hs_codes=hs_codes,
            ),
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
    """Drop upload file + preview when MDI/TDI dataset changes."""
    clear_upload_preview_cache()
    st.session_state.pop("dash_sidebar_upload", None)
    st.session_state.pop("dash_last_merge_token", None)
    st.session_state.pop(_UPLOAD_FILE_TOKEN_KEY, None)
    st.session_state.dash_merge_requested = False
    if reset_source_mode:
        st.session_state.dash_source_mode = "Use default file"


def ensure_upload_preview_dashboard(uploaded, *, hs_codes: list[str] | None) -> bool:
    """Load upload-only rows into dashboard_df so tabs work before merge."""
    if uploaded is None:
        return False

    preview = get_upload_preview(uploaded)
    if preview is None or preview.already_merged or preview.dataset_mismatch:
        if preview is not None and preview.error:
            st.session_state.dashboard_df = None
            st.session_state.dashboard_ml_ready = False
            st.session_state.pop(_UPLOAD_DATASET_MODE_KEY, None)
        return False

    if preview.error:
        st.session_state.dashboard_df = None
        st.session_state.dashboard_ml_ready = False
        return False

    if not preview.ml_ready or not preview.processed_csv:
        st.session_state.dashboard_df = None
        st.session_state.dashboard_ml_ready = False
        return False

    token = _upload_token(uploaded)
    mode = _normalize_dataset_mode(st.session_state.get("analysis_mode", "MDI"))
    dashboard_cache_token = f"{token}|{mode}"
    source_name = upload_preview_source_name(uploaded.name)
    if (
        st.session_state.get("dashboard_source") == source_name
        and st.session_state.get(_UPLOAD_PREVIEW_TOKEN_KEY) == dashboard_cache_token
        and st.session_state.get(_UPLOAD_DATASET_MODE_KEY) == mode
        and get_dataframe() is not None
    ):
        return True

    temp = temp_file_path("preview", uploaded.name)
    hs = hs_codes or ANALYSIS_HS_CODE_OPTIONS.get(mode, ANALYSIS_HS_CODE_OPTIONS["MDI"])
    with st.spinner("Loading upload for dashboards…"):
        df = load_upload_for_dashboard(temp, hs_codes=hs)
    msg = (
        f"Upload preview · {len(df):,} rows — dashboards show **this file only**. "
        f"Click **Update data** to merge into the saved dataset."
    )
    if preview.merge_block_reason:
        msg = (
            f"Upload preview · {len(df):,} rows — dashboards show **this file only**. "
            f"**Update data** is disabled: {preview.merge_block_reason}"
        )
    finish_dashboard_load(df, source_name, message=msg)
    st.session_state[_UPLOAD_PREVIEW_TOKEN_KEY] = dashboard_cache_token
    st.session_state[_UPLOAD_DATASET_MODE_KEY] = mode
    return True


def _preview_expander_label(preview: UploadPreviewResult) -> str:
    if preview.error:
        return "Upload · Error"
    if preview.already_merged:
        return "Upload · Already merged"
    if preview.ml_ready:
        status = f"{preview.row_count:,} rows"
        if preview.upload_coverage:
            status += f" · {preview.upload_coverage}"
        return f"Upload · Ready · {status}"
    missing = len(preview.missing_ml_columns) or 3
    return f"Upload · Missing ML columns ({missing})"


def _render_upload_preview_details(preview: UploadPreviewResult) -> None:
    if preview.error:
        st.error(preview.error)
        return

    if preview.already_merged:
        st.info("This file was already merged. Upload a different file or change the file to update again.")
        return

    if preview.ml_ready:
        st.success("Ready for analytics — BRAND NAME, SUPPLIER, TYPE present.")
        st.caption("Dashboards use **upload data only** until you click **Update data**.")
    else:
        missing = ", ".join(preview.missing_ml_columns) or f"{COL_BRAND_NAME}, {COL_SUPPLIER}, {COL_TYPE}"
        st.error(f"Missing or empty: **{missing}**")
        st.caption("Run the ML Predict app first, then upload the prediction CSV.")

    if preview.merge_block_reason:
        st.warning(preview.merge_block_reason)

    st.markdown(f"- **File type:** {preview.file_kind}")
    st.markdown(f"- **Rows after ingest:** {preview.row_count:,}")
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
        st.caption("Download the ingested file (rows kept after marked_for_delete filter).")
        st.download_button(
            "Download processed file",
            data=preview.processed_csv,
            file_name=preview.processed_download_name,
            mime="text/csv",
            use_container_width=True,
            key="dash_download_processed_upload",
            disabled=preview.already_merged,
            help="Same rows that Update data would merge — does not change your dataset.",
        )


def render_upload_preview_panel(uploaded) -> bool:
    """
    Collapsible upload validation summary.
    Returns True when Update data should be enabled.
    """
    if uploaded is None:
        st.caption("Upload an ML prediction CSV (same format as predictions_pmdi_etl.csv).")
        return False

    preview = get_upload_preview(uploaded)
    if preview is None:
        return False

    expand = bool(preview.error or not preview.ml_ready or preview.merge_block_reason)
    with st.expander(_preview_expander_label(preview), expanded=expand):
        _render_upload_preview_details(preview)

    if preview.error or preview.dataset_mismatch:
        return False

    return preview.ready_for_merge
