"""
MDI Material Intelligence Platform
Streamlit dashboard: Import Analytics (ETL + Analysis) → Train → Predict
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from config.settings import (
    APP_CONFIG_DIR,
    DATA_DIR,
    DEFAULT_DATASETS_DIR,
    DEFAULT_MODEL_DIR,
    PROJECT_ROOT,
    TEMP_DIR,
)
from services.data_paths import (
    list_user_data_files,
    migrate_storage_layout,
    resolve_analysis_dataset,
    temp_file_path,
)
from ui.predict_page import render_predict_page
from ui.train_page import render_train_page
from ui.analysis import render_analysis_page
from ui.analysis_data import apply_data_source_selection
from ui.sidebar_analysis import (
    render_analysis_sidebar,
    render_back_to_analysis_sidebar,
    sync_dataset_mode_from_sidebar,
)
from ui.theme import (
    BRAND,
    hero,
    inject_theme,
    section_header,
)

st.set_page_config(
    page_title="MDI Intelligence Platform",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_theme()

def init_session_state():
    defaults = {
        "active_df": None,
        "active_df_name": None,
        "last_predictions": None,
        "model_dir": str(DEFAULT_MODEL_DIR),
        "predict_product_line": "PMDI",
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
        "analysis_subtab": "market",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
    for key in ("analysis_mode", "sidebar_analysis_mode"):
        if st.session_state.get(key) == "PMDI":
            st.session_state[key] = "MDI"


def list_data_files() -> list[Path]:
    """CSV/Excel under data/ only — excludes app_config files and temp _upload_* files."""
    return list_user_data_files()


def set_active_df(df: pd.DataFrame, name: str):
    st.session_state.active_df = df
    st.session_state.active_df_name = name


def load_dataset_selector(key_prefix: str, label: str = "Select dataset"):
    from services.data_loader_service import load_file

    files = list_data_files()
    options = ["— Upload or use session data —"] + [f.name for f in files]
    choice = st.selectbox(label, options, key=f"{key_prefix}_file_select")
    uploaded = st.file_uploader("Or upload CSV / Excel", type=["csv", "xlsx", "xls"], key=f"{key_prefix}_upload")

    if uploaded is not None:
        upload_path = temp_file_path(key_prefix, uploaded.name)
        upload_path.write_bytes(uploaded.getvalue())
        st.session_state[f"{key_prefix}_source_path"] = str(upload_path)
        return load_file(upload_path), uploaded.name

    if choice != options[0]:
        file_path = DATA_DIR / choice
        st.session_state[f"{key_prefix}_source_path"] = str(file_path)
        return load_file(file_path), choice

    if st.session_state.active_df is not None:
        if st.checkbox(
            f"Use session dataset ({st.session_state.active_df_name or 'in memory'})",
            value=True,
            key=f"{key_prefix}_use_session",
        ):
            return st.session_state.active_df.copy(), st.session_state.active_df_name
    return None, None


def try_plotly_bar(df: pd.DataFrame, x: str, y: str, title: str, color: str | None = None):
    if df.empty:
        st.info("No data available for this chart.")
        return
    try:
        import plotly.express as px

        fig = px.bar(
            df, x=x, y=y, title=title,
            color_discrete_sequence=[color or BRAND["accent"]],
            template="plotly_white",
        )
        fig.update_layout(height=360, margin=dict(l=20, r=20, t=48, b=20))
        st.plotly_chart(fig, use_container_width=True)
    except ImportError:
        st.bar_chart(df.set_index(x)[y])


def render_sidebar() -> str:
    with st.sidebar:
        st.markdown(
            """
            <div class="sidebar-brand">
                <h2>VietNam Market</h2>
                <span>Chemical Trade Intelligence</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        nav_page = st.session_state.get("nav_page", "insights")
        if nav_page == "insights":
            render_analysis_sidebar()
        elif nav_page == "train":
            st.markdown('<p class="sidebar-section-label">Train model</p>', unsafe_allow_html=True)
            st.caption("Configure training data and hyperparameters in the main panel.")
            render_back_to_analysis_sidebar()
        elif nav_page == "predict":
            st.markdown('<p class="sidebar-section-label">Predict new</p>', unsafe_allow_html=True)
            st.caption("Run inference on import data in the main panel.")
            render_back_to_analysis_sidebar()

        st.caption(f"© {datetime.now().year} · MDI Platform")

    return st.session_state.get("nav_page", "insights")


def _analysis_mode() -> str:
    mode = st.session_state.get("analysis_mode", "MDI")
    return "MDI" if mode == "PMDI" else mode


def page_overview():
    hero("MDI Intelligence Platform", "Analyze Vietnam chemical imports, train models, and predict materials.")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Data files", len(list_data_files()))
    n = len(st.session_state.dashboard_df) if st.session_state.get("dashboard_df") is not None else 0
    c2.metric("Analytics rows", f"{n:,}" if n else "—")
    c3.metric("Model", "Ready" if Path(st.session_state.model_dir, "model.pt").exists() else "Missing")
    mode = _analysis_mode()
    seed_path = resolve_analysis_dataset(mode)
    c4.metric("Default analysis file", seed_path.name[:24] + "…")

    st.markdown(
        """
        | Step | Module | Description |
        |:---:|--------|-------------|
        | 1 | **Import Analytics** | Load or upload CSV → auto ETL → dashboard with filters & YoY/MoM/QoQ/YTD |
        | 2 | **Train Model** | Labeled data with `BRAND NAME`, `TYPE`, `SUPPLIER` |
        | 3 | **Prediction** | Fill `BRAND NAME`, `TYPE`, `SUPPLIER` when missing |
        """
    )
    if st.button("Open Import Analytics", type="primary", use_container_width=True):
        st.session_state.nav_page = "insights"
        st.rerun()


def page_train():
    render_train_page(list_data_files)


def page_predict():
    render_predict_page(load_dataset_selector, set_active_df)


def page_settings():
    hero("Settings", "Paths and session")
    from config.settings import ANALYSIS_DATASET_OPTIONS, PREDICTION_MODEL_OPTIONS

    st.code(
        f"Project: {PROJECT_ROOT}\n"
        f"User data: {DATA_DIR}\n"
        f"App datasets (MDI/TDI seeds): {DEFAULT_DATASETS_DIR}\n"
        f"Temp uploads: {TEMP_DIR}\n"
        f"App config: {APP_CONFIG_DIR}",
        language="text",
    )
    mode = _analysis_mode()
    st.markdown(
        f"- Analysis mode: `{mode}`\n"
        f"- MDI model: `{PREDICTION_MODEL_OPTIONS['PMDI']}`\n"
        f"- TDI model: `{PREDICTION_MODEL_OPTIONS['TDI']}`\n"
        f"- Row delete rules: `config/settings.py` (DESCRIPTION_BLACKLIST_*)\n"
        f"- MDI seed: `{ANALYSIS_DATASET_OPTIONS['MDI']}` (app_data/)\n"
        f"- TDI seed: `{ANALYSIS_DATASET_OPTIONS['TDI']}` (app_data/)\n"
        f"- User merge target: `data/` (same filenames after Update data)"
    )
    if st.button("Clear analytics session"):
        for k in ("dashboard_df", "dashboard_df_name", "dashboard_msg", "active_df", "active_df_name"):
            st.session_state[k] = None
        st.rerun()


def main():
    init_session_state()
    migrate_storage_layout()
    from config.settings import ANALYSIS_HS_CODE_OPTIONS

    mode = _analysis_mode()
    if st.session_state.get("nav_page", "insights") == "insights":
        sync_dataset_mode_from_sidebar()
        apply_data_source_selection(
            dataset_mode=mode,
            hs_codes=ANALYSIS_HS_CODE_OPTIONS.get(mode, ANALYSIS_HS_CODE_OPTIONS["MDI"]),
        )
    page = render_sidebar()
    routes = {
        "overview": page_overview,
        "insights": lambda: render_analysis_page(
            set_active_df,
            dataset_mode=mode,
            dataset_label=mode,
            hs_codes=ANALYSIS_HS_CODE_OPTIONS.get(mode, ANALYSIS_HS_CODE_OPTIONS["MDI"]),
        ),
        "train": page_train,
        "predict": page_predict,
        "settings": page_settings,
    }
    routes.get(page, routes["insights"])()


if __name__ == "__main__":
    main()
