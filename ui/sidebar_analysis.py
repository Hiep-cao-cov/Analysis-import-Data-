"""Contextual sidebar controls for Data Analysis (shared data + per-tab options)."""

from __future__ import annotations



import streamlit as st



from config.settings import ANALYSIS_DATASET_OPTIONS, SALE_CHANNEL_FILTER_OPTIONS
from services.analysis_service import filter_options
from services.customer_filter_service import (
    customer_id_to_name,
    resolve_customer_filter_options,
)
from services.supplier_filter_service import resolve_supplier_filter_options

from ui.sidebar_nav import sidebar_nav_button
from ui.theme import format_customer_display_name



ANALYSIS_SUBTAB_LABELS = {

    "market": "Market overview",

    "supplier": "Supplier deep dive",

    "customer": "Customer deep dive",

}





def get_analysis_subtab_label() -> str:

    """Page title matching the sidebar Analysis mode selection."""

    key = st.session_state.get("analysis_subtab", "market")

    return ANALYSIS_SUBTAB_LABELS.get(key, "Market overview")





def render_analysis_subtab_selector() -> str:

    """Return active analysis subtab key: market | supplier | customer."""

    keys = list(ANALYSIS_SUBTAB_LABELS.keys())

    current = st.session_state.get("analysis_subtab", "market")

    if current not in keys:

        st.session_state.analysis_subtab = "market"

        current = "market"



    return st.radio(

        "Dashboard",

        options=keys,

        index=keys.index(current),

        format_func=lambda k: ANALYSIS_SUBTAB_LABELS[k],

        key="analysis_subtab",

        label_visibility="collapsed",

    )





def render_tab_options_inside_analysis_mode(subtab: str) -> None:

    """Per-tab controls nested under Analysis mode expander."""

    st.markdown("---")

    if subtab in ("market", "supplier", "customer"):

        st.checkbox("Show detail data", key="show_detail_data")





def _get_market_overview_sidebar_options() -> tuple[list[str], list[str]]:
    df = st.session_state.get("dashboard_df")
    if df is None or df.empty:
        return [], []

    opts = filter_options(df)
    years = opts.get("years", [])
    types = _get_material_types()
    _sync_material_type_for_dataset()

    dataset_label = _normalize_analysis_dataset_mode(
        st.session_state.get("analysis_mode", "MDI")
    )
    material_type = st.session_state.get(ANALYSIS_FILTER_MTYPE)
    if not material_type or (types and material_type not in types):
        material_type = _default_material_type_for_dataset(types) if types else ""
    sale_channel = st.session_state.get(
        "analysis_sale_channel",
        SALE_CHANNEL_FILTER_OPTIONS[0],
    )

    suppliers = resolve_supplier_filter_options(
        df,
        dataset_label=dataset_label,
        material_type=material_type,
        sale_channel=sale_channel,
    )
    return years, suppliers


_FILTER_DATASET_SIG_KEY = "_filter_dataset_sig"
# Shared across Market overview (Tab 1) and Supplier deep dive (Tab 2)
ANALYSIS_FILTER_YEAR = "analysis_year"
ANALYSIS_FILTER_SUPPLIER = "analysis_supplier"
ANALYSIS_FILTER_CUSTOMER = "analysis_customer"
ANALYSIS_FILTER_MTYPE = "analysis_mtype"
_LEGACY_FILTER_KEYS = (
    "dash_mtype",
    "sup_mtype",
    "dash_year",
    "dash_supplier",
    "sup_year",
    "sup_supplier",
)


def _normalize_analysis_dataset_mode(mode: str) -> str:
    """Map legacy session value PMDI → MDI (dataset selectbox label)."""
    m = str(mode).strip().upper()
    if m == "PMDI":
        return "MDI"
    return m


def _default_material_type_for_dataset(types: list[str]) -> str:
    """Default material type for the active MDI/TDI dataset file."""
    if not types:
        return ""
    mode = _normalize_analysis_dataset_mode(
        st.session_state.get("analysis_mode", "MDI")
    )
    if mode == "MDI":
        for pref in ("PMDI", "MMDI"):
            for t in types:
                if str(t).strip().upper() == pref:
                    return t
    if mode == "TDI":
        for t in types:
            if "TDI" in str(t).strip().upper():
                return t
    return types[0]


def _migrate_legacy_analysis_filter_keys() -> None:
    """One-time copy from old per-tab keys to shared analysis filter keys."""
    if ANALYSIS_FILTER_YEAR not in st.session_state:
        for key in ("dash_year", "sup_year"):
            if st.session_state.get(key) is not None:
                st.session_state[ANALYSIS_FILTER_YEAR] = st.session_state[key]
                break
    if ANALYSIS_FILTER_SUPPLIER not in st.session_state:
        for key in ("dash_supplier", "sup_supplier"):
            if st.session_state.get(key) is not None:
                st.session_state[ANALYSIS_FILTER_SUPPLIER] = st.session_state[key]
                break
    if ANALYSIS_FILTER_MTYPE not in st.session_state:
        for key in ("dash_mtype", "sup_mtype"):
            if st.session_state.get(key) is not None:
                st.session_state[ANALYSIS_FILTER_MTYPE] = st.session_state[key]
                break


def sync_dataset_mode_from_sidebar() -> bool:
    """
    Apply the Dataset selectbox (sidebar_analysis_mode) to analysis_mode before data load.
    Returns True when the active dataset changed.
    """
    options = list(ANALYSIS_DATASET_OPTIONS.keys())
    selected = _normalize_analysis_dataset_mode(
        st.session_state.get("sidebar_analysis_mode", "MDI")
    )
    if selected not in options:
        st.session_state.sidebar_analysis_mode = _normalize_analysis_dataset_mode(
            st.session_state.get("analysis_mode", "MDI")
        )
        return False
    current = _normalize_analysis_dataset_mode(st.session_state.get("analysis_mode", "MDI"))
    if selected == current:
        return False
    st.session_state.analysis_mode = selected
    st.session_state.sidebar_analysis_mode = selected
    st.session_state.dashboard_df = None
    st.session_state.dashboard_source = None
    st.session_state.active_df = None
    st.session_state.active_df_name = None
    st.session_state.dashboard_msg = None
    _reset_analysis_filters_for_dataset_change()
    return True


def _reset_analysis_filters_for_dataset_change() -> None:
    """Clear filter widgets so they re-bind to the newly loaded dataset."""
    for key in (
        ANALYSIS_FILTER_YEAR,
        ANALYSIS_FILTER_SUPPLIER,
        ANALYSIS_FILTER_CUSTOMER,
        ANALYSIS_FILTER_MTYPE,
        *_LEGACY_FILTER_KEYS,
    ):
        st.session_state.pop(key, None)
    st.session_state.pop(_FILTER_DATASET_SIG_KEY, None)


def _sync_material_type_for_dataset() -> None:
    """Reset material-type keys when dataset changes. Must run before any filter widgets."""
    mode = _normalize_analysis_dataset_mode(st.session_state.get("analysis_mode", "MDI"))
    source = str(st.session_state.get("dashboard_source", ""))
    types = _get_material_types()
    sig = f"{mode}|{source}|{'|'.join(types)}"
    if st.session_state.get(_FILTER_DATASET_SIG_KEY) == sig:
        return
    st.session_state[_FILTER_DATASET_SIG_KEY] = sig
    if types:
        st.session_state[ANALYSIS_FILTER_MTYPE] = _default_material_type_for_dataset(types)


def _ensure_year_supplier_keys(
    years: list,
    suppliers: list,
    *,
    year_key: str,
    supplier_key: str,
) -> None:
    """Align year/supplier session values with options. Call only before their selectboxes."""
    if years and st.session_state.get(year_key) not in years:
        st.session_state[year_key] = years[-1]
    if suppliers and st.session_state.get(supplier_key) not in suppliers:
        st.session_state[supplier_key] = suppliers[0]


def _get_material_types() -> list[str]:
    df = st.session_state.get("dashboard_df")
    if df is None or df.empty:
        return []
    opts = filter_options(df)
    types = [
        t
        for t in opts.get("material_types", [])
        if str(t).strip() and str(t).lower() not in ("unspecified", "nan")
    ]
    if not types and "type_clean" in df.columns:
        types = sorted(df["type_clean"].dropna().unique().tolist(), key=str)
    return types


def _sale_channel_selectbox(*, key: str = "analysis_sale_channel") -> None:
    st.selectbox(
        "Sale channel",
        SALE_CHANNEL_FILTER_OPTIONS,
        key=key,
    )


def _material_type_selectbox(types: list[str], *, key: str) -> None:
    if not types:
        return
    if st.session_state.get(key) not in types:
        st.session_state[key] = _default_material_type_for_dataset(types)
    st.selectbox(
        "Material type (from file)",
        types,
        key=key,
    )


def _render_overview_filter_expander(expander_title: str) -> None:
    """Shared sidebar filters for Tab 1 and Tab 2 (same session keys)."""
    _migrate_legacy_analysis_filter_keys()
    years, suppliers = _get_market_overview_sidebar_options()
    types = _get_material_types()
    if not years or not suppliers:
        return

    _ensure_year_supplier_keys(
        years,
        suppliers,
        year_key=ANALYSIS_FILTER_YEAR,
        supplier_key=ANALYSIS_FILTER_SUPPLIER,
    )

    current_year = st.session_state.get(ANALYSIS_FILTER_YEAR, years[-1])
    current_supplier = st.session_state.get(ANALYSIS_FILTER_SUPPLIER, suppliers[0])

    with st.expander(expander_title, expanded=True):
        _sale_channel_selectbox(key="analysis_sale_channel")
        st.selectbox(
            "Year",
            years,
            index=years.index(current_year) if current_year in years else len(years) - 1,
            key=ANALYSIS_FILTER_YEAR,
        )
        st.selectbox(
            "Supplier",
            suppliers,
            index=suppliers.index(current_supplier)
            if current_supplier in suppliers
            else 0,
            key=ANALYSIS_FILTER_SUPPLIER,
        )
        _material_type_selectbox(types, key=ANALYSIS_FILTER_MTYPE)


def _ensure_customer_key(
    customer_ids: list[str],
    *,
    customer_key: str,
) -> None:
    if customer_ids and st.session_state.get(customer_key) not in customer_ids:
        st.session_state[customer_key] = customer_ids[0]


def _searchable_customer_selectbox(
    customer_ids: list[str],
    id_to_name: dict[str, str],
    *,
    key: str,
    label: str = "Customer",
) -> None:
    st.selectbox(
        label,
        customer_ids,
        format_func=lambda cid: format_customer_display_name(id_to_name.get(cid, cid), max_len=64),
        key=key,
        filter_mode="contains",
        placeholder="Type to search customer…",
        help="Open the list and type to filter by customer name.",
    )


def _get_customer_sidebar_options() -> tuple[list[str], list[tuple[str, str]]]:
    df = st.session_state.get("dashboard_df")
    if df is None or df.empty:
        return [], []

    opts = filter_options(df)
    years = opts.get("years", [])
    types = _get_material_types()
    _sync_material_type_for_dataset()

    material_type = st.session_state.get(ANALYSIS_FILTER_MTYPE)
    if not material_type or (types and material_type not in types):
        material_type = _default_material_type_for_dataset(types) if types else ""
    sale_channel = st.session_state.get(
        "analysis_sale_channel",
        SALE_CHANNEL_FILTER_OPTIONS[0],
    )
    year_raw = st.session_state.get(ANALYSIS_FILTER_YEAR)
    year_int = int(year_raw) if year_raw is not None and str(year_raw).isdigit() else None
    if year_int is None and years:
        year_int = int(years[-1])

    ensure_ids: list[str] = []
    current = st.session_state.get(ANALYSIS_FILTER_CUSTOMER)
    if current:
        ensure_ids.append(str(current))

    customer_options = resolve_customer_filter_options(
        df,
        material_type=material_type,
        sale_channel=sale_channel,
        year=year_int,
        ensure_ids=ensure_ids,
    )
    return years, customer_options


def render_customer_overview_filters() -> None:
    if not (
        st.session_state.get("nav_page", "insights") == "insights"
        and st.session_state.get("analysis_subtab", "market") == "customer"
    ):
        return

    _migrate_legacy_analysis_filter_keys()
    years, customer_options = _get_customer_sidebar_options()
    types = _get_material_types()
    if not years or not customer_options:
        return

    customer_ids = [cid for cid, _ in customer_options]
    id_to_name = customer_id_to_name(customer_options)
    _ensure_customer_key(customer_ids, customer_key=ANALYSIS_FILTER_CUSTOMER)

    current_year = st.session_state.get(ANALYSIS_FILTER_YEAR, years[-1])

    with st.expander(":orange[Customer overview filters]", expanded=True):
        _sale_channel_selectbox(key="analysis_sale_channel")
        st.selectbox(
            "Year",
            years,
            index=years.index(current_year) if current_year in years else len(years) - 1,
            key=ANALYSIS_FILTER_YEAR,
        )
        _searchable_customer_selectbox(
            customer_ids,
            id_to_name,
            key=ANALYSIS_FILTER_CUSTOMER,
        )
        _material_type_selectbox(types, key=ANALYSIS_FILTER_MTYPE)


def render_market_overview_filters() -> None:
    if not (
        st.session_state.get("nav_page", "insights") == "insights"
        and st.session_state.get("analysis_subtab", "market") == "market"
    ):
        return
    _render_overview_filter_expander(":orange[Market overview filters]")


def render_supplier_overview_filters() -> None:
    if not (
        st.session_state.get("nav_page", "insights") == "insights"
        and st.session_state.get("analysis_subtab", "market") == "supplier"
    ):
        return
    _render_overview_filter_expander(":orange[Supplier overview filters]")


def render_shared_data_sidebar() -> None:

    """Dataset and upload — used by all analysis tabs."""

    st.selectbox(
        "Dataset",
        options=list(ANALYSIS_DATASET_OPTIONS.keys()),
        key="sidebar_analysis_mode",
    )

    prev_mode = st.session_state.get("dash_source_mode", "Use default file")

    source_mode = st.radio(

        "Data source",

        options=["Use default file", "Upload new file"],

        index=0 if prev_mode == "Use default file" else 1,

        key="dash_source_mode",

    )

    if source_mode != prev_mode:

        st.session_state.dashboard_df = None

        st.session_state.dashboard_source = None

        st.session_state.active_df = None

        st.session_state.active_df_name = None

        st.session_state.dashboard_msg = None

        st.session_state.dash_last_merge_token = None

        st.session_state.dash_merge_requested = False

        _reset_analysis_filters_for_dataset_change()



    if source_mode == "Upload new file":

        st.file_uploader(

            "Upload CSV / Excel",

            type=["csv", "xlsx", "xls"],

            key="dash_sidebar_upload",

        )

        if st.button("Update data", key="dash_update_data_btn", use_container_width=True):

            st.session_state.dash_merge_requested = True

    with st.expander("Customer short names", expanded=False):
        from ui.customer_list_panel import render_customer_list_panel

        render_customer_list_panel()





def render_ml_tools_section() -> None:

    """Train / Predict — content inside the Model tools expander."""

    st.caption(

        "Analytics need BRAND NAME, SUPPLIER, and TYPE. "

        "Run **Predict new** if your upload is missing them."

    )

    sidebar_nav_button("Train Model", "train", key_suffix="_ml")

    sidebar_nav_button("Predict new", "predict", key_suffix="_ml")





def render_analysis_sidebar() -> str:

    """Full Data Analysis sidebar — three collapsible sections matching the same pattern."""

    _migrate_legacy_analysis_filter_keys()

    with st.expander(":green[Analysis mode]", expanded=True):
        subtab = render_analysis_subtab_selector()
        render_tab_options_inside_analysis_mode(subtab)

    with st.expander(":blue[Dataset & data source]", expanded=True):
        render_shared_data_sidebar()

    render_market_overview_filters()
    render_supplier_overview_filters()
    render_customer_overview_filters()

    with st.expander(":red[Model tools]", expanded=False):
        render_ml_tools_section()



    return st.session_state.get("analysis_subtab", "market")





def render_back_to_analysis_sidebar() -> None:

    st.markdown("---")

    sidebar_nav_button("← Back to Data Analysis", "insights", key_suffix="_back")


