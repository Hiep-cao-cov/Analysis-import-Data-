"""Data Analysis router: shared data load + tab pages."""
from __future__ import annotations

import streamlit as st

from services.data_paths import default_dashboard_dataset_path, resolve_analysis_dataset
from services.ml_columns import has_ml_target_columns
from ui.analysis_data import (
    get_dataframe,
    render_ml_columns_required_message,
)
from ui.dashboard_customer import render_customer_page
from ui.dashboard_market import render_market_page
from ui.dashboard_supplier import render_supplier_page


def render_upload_pending_message() -> None:
    """Main-area hint when Upload new file is selected but dashboards are not ready yet."""
    uploaded = st.session_state.get("dash_sidebar_upload")
    if uploaded is None:
        st.info(
            "Upload a CSV or Excel file in the sidebar (**Dataset & data source**). "
            "After ETL, dashboards will show **upload data only** until you click **Update data**."
        )
        return

    if not st.session_state.get("dashboard_ml_ready", False):
        from ui.upload_preview_panel import get_upload_preview

        preview = get_upload_preview(uploaded) if uploaded is not None else None
        if preview is not None and preview.dataset_mismatch:
            st.warning(preview.error or "This upload does not match the selected dataset.")
            return
        if preview is not None and preview.error:
            st.error(preview.error)
            return
        if preview is not None and preview.ml_ready and preview.merge_block_reason:
            st.info(
                f"Upload is valid ({preview.row_count:,} rows with **BRAND NAME**, **SUPPLIER**, **TYPE**). "
                f"Dashboards show upload data only. Merge is blocked: {preview.merge_block_reason}"
            )
            return
        st.warning(
            "This upload is missing **BRAND NAME**, **SUPPLIER**, or **TYPE** "
            "(see sidebar preview). Run **Predict new** in the ML app, then upload the prediction CSV."
        )


def render_analysis_page(
    set_active_df,
    dataset_mode: str,
    dataset_label: str = "MDI",
    hs_codes: list[str] | None = None,
) -> None:
    # Data load runs in app.main() via apply_data_source_selection (before sidebar widgets).

    source_mode = st.session_state.get("dash_source_mode", "Use default file")
    load_path = (
        default_dashboard_dataset_path(dataset_mode)
        if source_mode == "Use default file"
        else resolve_analysis_dataset(dataset_mode)
    )
    df = get_dataframe()
    if df is None:
        if source_mode == "Upload new file":
            render_upload_pending_message()
            return
        if not load_path.exists():
            st.error(
                f"Place seed data in `app_data/{load_path.name}` or upload a file in the sidebar. "
                f"Merged updates are saved under `data/{load_path.name}`."
            )
        else:
            render_ml_columns_required_message()
        return

    if not has_ml_target_columns(df):
        render_ml_columns_required_message(df)
        return

    set_active_df(df, st.session_state.get("dashboard_source", "data"))

    subtab = st.session_state.get("analysis_subtab", "market")
    if subtab == "supplier":
        render_supplier_page(df, dataset_label)
    elif subtab == "customer":
        render_customer_page(df, dataset_label)
    else:
        render_market_page(df, dataset_label)
