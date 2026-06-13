"""Data Analysis router: shared data load + tab pages."""
from __future__ import annotations

import streamlit as st

from services.data_paths import resolve_analysis_dataset
from services.ml_columns import has_ml_target_columns
from ui.analysis_data import (
    apply_data_source_selection,
    get_dataframe,
    render_ml_columns_required_message,
)
from ui.dashboard_customer import render_customer_page
from ui.dashboard_market import render_market_page
from ui.dashboard_supplier import render_supplier_page


def render_analysis_page(
    set_active_df,
    dataset_mode: str,
    dataset_label: str = "MDI",
    hs_codes: list[str] | None = None,
) -> None:
    apply_data_source_selection(dataset_mode, hs_codes=hs_codes)

    load_path = resolve_analysis_dataset(dataset_mode)
    df = get_dataframe()
    if df is None:
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


def render_dashboard_page(
    set_active_df,
    dataset_mode: str,
    dataset_label: str = "MDI",
    hs_codes: list[str] | None = None,
) -> None:
    """Backwards-compatible alias for the analysis router."""
    render_analysis_page(set_active_df, dataset_mode, dataset_label=dataset_label, hs_codes=hs_codes)
