"""
MDI Data Analysis — standalone Import Analytics (Market / Supplier / Customer).
Run: streamlit run app.py   (from this folder)
"""
from __future__ import annotations

from datetime import datetime

import streamlit as st

from config.settings import (
    ANALYSIS_DATASET_OPTIONS,
    ANALYSIS_HS_CODE_OPTIONS,
    APP_CONFIG_DIR,
    DATA_DIR,
    DEFAULT_DATASETS_DIR,
    PROJECT_ROOT,
    TEMP_DIR,
    UPLOAD_SKIP_DESCRIPTION_BLACKLIST_DEFAULT,
)
from services.data_paths import clear_temp_dir_on_startup, migrate_storage_layout
from ui.analysis import render_analysis_page
from ui.analysis_data import apply_data_source_selection
from ui.sidebar_analysis import render_analysis_sidebar, sync_dataset_mode_from_sidebar
from ui.theme import inject_theme

st.set_page_config(
    page_title="MDI Data Analysis",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_theme()


def init_session_state() -> None:
    defaults = {
        "nav_page": "insights",
        "dashboard_df": None,
        "dashboard_df_name": None,
        "dashboard_msg": None,
        "analysis_mode": "MDI",
        "sidebar_analysis_mode": "MDI",
        "dash_source_mode": "Use default file",
        "show_detail_data": False,
        "dash_last_merge_token": None,
        "dash_merge_requested": False,
        "dash_skip_description_blacklist": UPLOAD_SKIP_DESCRIPTION_BLACKLIST_DEFAULT,
        "analysis_subtab": "market",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
    for key in ("analysis_mode", "sidebar_analysis_mode"):
        if st.session_state.get(key) == "PMDI":
            st.session_state[key] = "MDI"
    valid_datasets = list(ANALYSIS_DATASET_OPTIONS.keys())
    sidebar_mode = st.session_state.get("sidebar_analysis_mode", "MDI")
    if sidebar_mode not in valid_datasets:
        fallback = st.session_state.get("analysis_mode", "MDI")
        st.session_state.sidebar_analysis_mode = (
            fallback if fallback in valid_datasets else valid_datasets[0]
        )


def _analysis_mode() -> str:
    mode = st.session_state.get("analysis_mode", "MDI")
    return "MDI" if mode == "PMDI" else mode


def _noop_set_active_df(df, name: str) -> None:
    """Analysis uses dashboard_df only — no cross-app session handoff."""
    pass


def page_settings() -> None:
    from ui.theme import hero

    hero("Settings", "Data Analysis app paths")
    st.code(
        f"App root: {PROJECT_ROOT}\n"
        f"User data: {DATA_DIR}\n"
        f"Seed datasets: {DEFAULT_DATASETS_DIR}\n"
        f"Temp uploads: {TEMP_DIR}\n"
        f"App config: {APP_CONFIG_DIR}",
        language="text",
    )
    mode = _analysis_mode()
    st.markdown(
        f"- Analysis mode: `{mode}`\n"
        f"- MDI seed: `{ANALYSIS_DATASET_OPTIONS['MDI']}`\n"
        f"- TDI seed: `{ANALYSIS_DATASET_OPTIONS['TDI']}`\n"
        f"- Row delete rules: `config/settings.py`\n"
        f"- Datasets must include **BRAND NAME**, **SUPPLIER**, **TYPE** "
        f"(from ML app prediction CSV or pre-labeled files)."
    )
    if st.button("Clear analytics session"):
        for k in ("dashboard_df", "dashboard_df_name", "dashboard_msg", "dash_unmapped_customers"):
            st.session_state[k] = None
        st.rerun()


def main() -> None:
    init_session_state()
    migrate_storage_layout()
    clear_temp_dir_on_startup()

    if st.session_state.get("nav_page", "insights") == "insights":
        sync_dataset_mode_from_sidebar()

    mode = _analysis_mode()

    # Load dataset before sidebar filters — overview expanders need dashboard_df.
    if st.session_state.get("nav_page", "insights") == "insights":
        apply_data_source_selection(
            dataset_mode=mode,
            hs_codes=ANALYSIS_HS_CODE_OPTIONS.get(mode, ANALYSIS_HS_CODE_OPTIONS["MDI"]),
        )

    with st.sidebar:
        st.markdown(
            """
            <div class="sidebar-brand">
                <h2>Data Analysis</h2>
                <span>Import Analytics · MDI / TDI</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        nav = st.radio(
            "Page",
            options=["insights", "settings"],
            format_func=lambda k: "Dashboard" if k == "insights" else "Settings",
            key="nav_page",
            label_visibility="collapsed",
        )
        if nav == "insights":
            render_analysis_sidebar()
        st.caption(f"© {datetime.now().year} · MDI Data Analysis")

    if nav == "insights":
        render_analysis_page(
            _noop_set_active_df,
            dataset_mode=mode,
            dataset_label=mode,
            hs_codes=ANALYSIS_HS_CODE_OPTIONS.get(mode, ANALYSIS_HS_CODE_OPTIONS["MDI"]),
        )
    else:
        page_settings()


if __name__ == "__main__":
    main()
