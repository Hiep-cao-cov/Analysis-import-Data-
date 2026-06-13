"""Tab 2 — Supplier deep dive: import volume and shipment detail for a supplier."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from config.settings import SALE_CHANNEL_FILTER_OPTIONS, SUPPLIER_TOP_CUSTOMER_OPTIONS
from services.analysis_service import MONTH_ORDER, filter_by_material_type, filter_options, resolve_type_column
from services.supplier_filter_service import (
    prepare_supplier_analysis_frame,
    resolve_supplier_filter_options,
)
from ui.chart_volume import (
    MONTH_DISPLAY,
    build_supplier_customer_new_current_data,
    build_supplier_top_customers_data,
    build_supplier_top_salers_data,
    format_dataset_year_range,
    render_monthly_supplier_market_volume_chart,
    render_quarterly_supplier_market_volume_chart,
    render_supplier_compare_dashboard,
    render_supplier_customer_new_current_stacked_chart,
    render_supplier_period_customer_volume_chart,
    render_supplier_top_customers_chart,
    render_supplier_top_salers_chart,
    render_yearly_supplier_market_volume_chart,
    supplier_color_map_for_material,
)
from ui.detail_table import prepare_shipment_detail_table, render_styled_table
from ui.sidebar_analysis import get_analysis_subtab_label
from ui.theme import (
    dashboard_header,
    format_customer_display_name,
    format_saler_display_name,
    format_supplier_display_name,
    format_supplier_sale_kpi_label,
    kpi_card,
    render_analysis_chip_row,
)

PERIOD_MODES = ["Yearly", "Quarterly", "Monthly"]


def _month_to_quarter(month: str) -> str:
    m = month.lower()
    if m in ("jan", "feb", "mar"):
        return "q1"
    if m in ("apr", "may", "jun"):
        return "q2"
    if m in ("jul", "aug", "sep"):
        return "q3"
    return "q4"


def _ensure_quarter_column(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    if "quarter" not in work.columns and "month" in work.columns:
        work["quarter"] = work["month"].astype(str).str.lower().map(
            lambda m: _month_to_quarter(m) if pd.notna(m) else None
        )
    return work


def _supplier_year_scope(
    df_channel: pd.DataFrame,
    *,
    supplier: str,
    supplier_col: str,
    material_type: str,
    type_col: str,
    year_int: int,
) -> pd.DataFrame:
    """Selected supplier + sidebar year — used for Top customers chart (always yearly)."""
    scoped = df_channel[df_channel[supplier_col].astype(str).str.strip() == str(supplier).strip()]
    scoped = filter_by_material_type(scoped, material_type, type_col=type_col)
    if "year" not in scoped.columns:
        return scoped
    return scoped[scoped["year"] == year_int].copy()


def _supplier_period_scope(
    df_channel: pd.DataFrame,
    *,
    supplier: str,
    supplier_col: str,
    material_type: str,
    type_col: str,
    period_mode: str,
    year_int: int,
) -> pd.DataFrame:
    """Rows for selected supplier matching the active Period mode scope."""
    scoped = df_channel[df_channel[supplier_col].astype(str).str.strip() == str(supplier).strip()]
    scoped = filter_by_material_type(scoped, material_type, type_col=type_col)
    if period_mode == "Yearly":
        return scoped
    if "year" not in scoped.columns:
        return scoped
    return scoped[scoped["year"] == year_int].copy()


def _render_period_controls(
    *,
    year: str,
    year_supplier_scope: pd.DataFrame,
) -> tuple[str, str, str | None, str | None]:
    """Period + optional quarter/month sub-select. Returns (mode, label, quarter, month)."""
    st.markdown(
        """
        <style>
        div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:has([data-testid="stSelectbox"]) {
            flex: 0 0 11rem !important;
            max-width: 11rem !important;
            width: 11rem !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    col_period, col_sub, _ = st.columns([1, 1, 6])
    with col_period:
        period_mode = st.selectbox(
            "Period",
            PERIOD_MODES,
            key="sup_period_mode",
        )
    selected_quarter: str | None = None
    selected_month: str | None = None
    if period_mode == "Quarterly":
        available = _quarters_with_data(year_supplier_scope)
        with col_sub:
            if available:
                current = st.session_state.get("sup_quarter_select")
                if current not in available:
                    st.session_state["sup_quarter_select"] = available[-1]
                selected_quarter = st.selectbox(
                    "Quarter",
                    available,
                    format_func=lambda q: str(q).upper(),
                    key="sup_quarter_select",
                )
            else:
                st.selectbox(
                    "Quarter",
                    ["—"],
                    disabled=True,
                    key="sup_quarter_select_empty",
                )
    elif period_mode == "Monthly":
        available = _months_with_data(year_supplier_scope)
        with col_sub:
            if available:
                current = st.session_state.get("sup_month_select")
                if current not in available:
                    st.session_state["sup_month_select"] = available[-1]
                selected_month = st.selectbox(
                    "Month",
                    available,
                    format_func=_month_display_label,
                    key="sup_month_select",
                )
            else:
                st.selectbox(
                    "Month",
                    ["—"],
                    disabled=True,
                    key="sup_month_select_empty",
                )
    return period_mode, f"Full year {year}", selected_quarter, selected_month


def _month_display_label(month_key: str) -> str:
    m = str(month_key).strip().lower()
    num = MONTH_ORDER.get(m)
    if num and 1 <= num <= 12:
        return MONTH_DISPLAY[num - 1]
    return str(month_key).upper()


def _months_with_data(df: pd.DataFrame) -> list[str]:
    """Months (jan–dec) present in scoped data, in calendar order."""
    if df.empty or "month" not in df.columns:
        return []
    present = {
        str(m).strip().lower()
        for m in df["month"].dropna().unique()
        if str(m).strip()
    }
    return sorted(present, key=lambda m: MONTH_ORDER.get(m, 99))


def _filter_month_scope(df: pd.DataFrame, month: str) -> pd.DataFrame:
    if df.empty or "month" not in df.columns:
        return df.iloc[0:0].copy()
    m = str(month).strip().lower()
    mask = df["month"].astype(str).str.strip().str.lower() == m
    return df.loc[mask].copy()


def _quarters_with_data(df: pd.DataFrame) -> list[str]:
    """Quarters (q1–q4) present in scoped data, in calendar order."""
    if df.empty or "quarter" not in df.columns:
        return []
    present = {
        str(q).strip().lower()
        for q in df["quarter"].dropna().unique()
        if str(q).strip()
    }
    return [q for q in ("q1", "q2", "q3", "q4") if q in present]


def _filter_quarter_scope(df: pd.DataFrame, quarter: str) -> pd.DataFrame:
    if df.empty or "quarter" not in df.columns:
        return df.iloc[0:0].copy()
    q = str(quarter).strip().lower()
    mask = df["quarter"].astype(str).str.strip().str.lower() == q
    return df.loc[mask].copy()


def _render_view_mode_controls(
    suppliers: list[str],
    primary_supplier: str,
) -> tuple[str, list[str]]:
    """Single-supplier deep dive vs multi-supplier compare mode."""
    view_mode = st.radio(
        "View",
        ["Single supplier", "Compare suppliers"],
        horizontal=True,
        key="sup_view_mode",
    )
    compare_suppliers: list[str] = []
    if view_mode == "Compare suppliers":
        defaults: list[str] = []
        if primary_supplier in suppliers:
            defaults.append(primary_supplier)
        for name in suppliers:
            if name not in defaults:
                defaults.append(name)
            if len(defaults) >= 2:
                break
        compare_suppliers = st.multiselect(
            "Suppliers to compare (2–5)",
            suppliers,
            default=defaults[: min(2, len(defaults))],
            key="sup_compare_suppliers",
        )
        compare_suppliers = compare_suppliers[:5]
        if len(compare_suppliers) < 2:
            st.info("Select at least **2 suppliers** to compare volume and market share.")
    return view_mode, compare_suppliers


def _render_top_customers_n_control() -> int:
    return int(
        st.selectbox(
            "Top customers",
            SUPPLIER_TOP_CUSTOMER_OPTIONS,
            format_func=lambda n: f"Top {n}",
            key="sup_top_customers_n",
        )
    )


def render_supplier_page(df: pd.DataFrame, dataset_label: str) -> None:
    df = _ensure_quarter_column(df)
    opts = filter_options(df)

    years = opts.get("years", [])
    supplier_col = "supplier_raw" if "supplier_raw" in df.columns else "supplier_group"
    types = [
        t
        for t in opts.get("material_types", [])
        if str(t).strip() and str(t).lower() not in ("unspecified", "nan")
    ]

    if not years:
        st.warning("No year column found in the file.")
        return
    if not types and "type_clean" in df.columns:
        types = sorted(df["type_clean"].dropna().unique().tolist(), key=str)

    sale_channel = st.session_state.get(
        "analysis_sale_channel",
        SALE_CHANNEL_FILTER_OPTIONS[0],
    )

    from ui.sidebar_analysis import ANALYSIS_FILTER_MTYPE, ANALYSIS_FILTER_SUPPLIER, ANALYSIS_FILTER_YEAR

    material_type = st.session_state.get(ANALYSIS_FILTER_MTYPE)
    if not material_type or material_type not in types:
        from ui.sidebar_analysis import _default_material_type_for_dataset

        material_type = _default_material_type_for_dataset(types) if types else ""

    suppliers = resolve_supplier_filter_options(
        df,
        dataset_label=dataset_label,
        material_type=material_type,
        sale_channel=sale_channel,
        supplier_col=supplier_col,
    )

    if not suppliers:
        st.warning("No suppliers match the current dataset, material type, and sale channel filters.")
        return

    dashboard_header(
        get_analysis_subtab_label(),
        f"Vietnam Chemical Import Intelligence · {dataset_label}",
    )
    if st.session_state.get("dashboard_msg"):
        st.success(st.session_state.dashboard_msg)

    year = st.session_state.get(ANALYSIS_FILTER_YEAR, years[-1] if years else "")
    supplier = st.session_state.get(ANALYSIS_FILTER_SUPPLIER, suppliers[0] if suppliers else "")
    if year not in years:
        year = years[-1] if years else year
    if supplier not in suppliers:
        supplier = suppliers[0] if suppliers else supplier

    render_analysis_chip_row(
        dataset_label=dataset_label,
        sale_channel=sale_channel,
        sale_channel_options=SALE_CHANNEL_FILTER_OPTIONS,
        year=year,
        supplier=supplier,
        show_supplier=st.session_state.get("sup_view_mode", "Single supplier") != "Compare suppliers",
    )

    year_int = int(year)
    type_col = resolve_type_column(df)
    df_channel = prepare_supplier_analysis_frame(
        df,
        dataset_label=dataset_label,
        material_type=material_type,
        sale_channel=sale_channel,
        type_col=type_col,
        supplier_col=supplier_col,
    )
    top_customers_scope = _supplier_year_scope(
        df_channel,
        supplier=supplier,
        supplier_col=supplier_col,
        material_type=material_type,
        type_col=type_col,
        year_int=year_int,
    )

    period_mode, period_label, selected_quarter, selected_month = _render_period_controls(
        year=year,
        year_supplier_scope=top_customers_scope,
    )
    view_mode, compare_suppliers = _render_view_mode_controls(suppliers, supplier)
    compare_mode = view_mode == "Compare suppliers" and len(compare_suppliers) >= 2
    top_customers_n = _render_top_customers_n_control() if not compare_mode else SUPPLIER_TOP_CUSTOMER_OPTIONS[0]

    period_scope = _supplier_period_scope(
        df_channel,
        supplier=supplier,
        supplier_col=supplier_col,
        material_type=material_type,
        type_col=type_col,
        period_mode=period_mode,
        year_int=year_int,
    )

    customers_chart_df, n_customers = build_supplier_top_customers_data(
        period_scope,
        top_n=top_customers_n,
    )
    salers_chart_df, n_salers = build_supplier_top_salers_data(
        top_customers_scope,
        top_n=top_customers_n,
    )
    total_ton = float(period_scope["volume_ton"].sum()) if not period_scope.empty else 0.0
    top_row = customers_chart_df.iloc[0] if not customers_chart_df.empty else None
    top_pct = float(top_row["share_pct"]) if top_row is not None else 0.0
    top_name = str(top_row["customer_label"]) if top_row is not None else "—"
    top_saler_row = salers_chart_df.iloc[0] if not salers_chart_df.empty else None
    top_saler_pct = float(top_saler_row["share_pct"]) if top_saler_row is not None else 0.0
    top_saler_name = str(top_saler_row["saler_label"]) if top_saler_row is not None else "—"

    if not compare_mode:
        m1, m2, m3, m4, m5 = st.columns(5)
        with m1:
            if period_mode == "Yearly":
                year_span = format_dataset_year_range(period_scope) or "period"
                channel_label = str(sale_channel).strip().lower()
                kpi_label = (
                    f"{format_supplier_display_name(supplier)} {material_type or '—'} "
                    f"sale {year_span} - {channel_label}"
                )
            else:
                kpi_label = format_supplier_sale_kpi_label(
                    supplier=supplier,
                    material_type=material_type or "—",
                    year=year,
                    sale_channel=sale_channel,
                )
            kpi_card(
                f"{total_ton:,.1f}",
                kpi_label,
                "◉",
                icon_class="green",
                label_variant="green-lg",
            )
        with m2:
            kpi_card(
                f"{n_customers:,}",
                "Customers in period",
                "◎",
                icon_class="blue",
            )
        with m3:
            kpi_card(
                f"{top_pct:.1f}%",
                f"Largest buyer · {format_customer_display_name(top_name, max_len=28)}",
                "◈",
                icon_class="gray",
            )
        with m4:
            kpi_card(
                f"{n_salers:,}",
                f"Salers in {year_int}",
                "◆",
                icon_class="blue",
            )
        with m5:
            kpi_card(
                f"{top_saler_pct:.1f}%",
                f"Largest saler · {format_saler_display_name(top_saler_name, max_len=24)}",
                "◇",
                icon_class="gray",
            )

    filter_sig = (
        sale_channel,
        year_int,
        supplier,
        material_type,
        period_label,
        period_mode,
        view_mode,
        top_customers_n,
        selected_quarter or "",
        selected_month or "",
        tuple(compare_suppliers) if compare_mode else (),
    )
    if st.session_state.get("sup_filter_sig") != filter_sig:
        st.session_state["sup_filter_sig"] = filter_sig

    supplier_colors = supplier_color_map_for_material(
        df_channel,
        material_type=material_type,
        type_col=type_col,
        supplier_col=supplier_col,
    )
    common_chart_kwargs = dict(
        material_type=material_type,
        selected_supplier=supplier,
        type_col=type_col,
        supplier_col=supplier_col,
    )

    top_customers_kwargs = dict(
        df=top_customers_scope,
        supplier=supplier,
        material_type=material_type,
        sale_channel=sale_channel,
        year_int=year_int,
        top_n=top_customers_n,
    )
    top_salers_kwargs = dict(top_customers_kwargs)

    if compare_mode:
        render_supplier_compare_dashboard(
            df_channel,
            material_type=material_type,
            suppliers=compare_suppliers,
            type_col=type_col,
            supplier_col=supplier_col,
            period_mode=period_mode,
            year_int=year_int,
            sale_channel=sale_channel,
            supplier_color_map=supplier_colors,
        )
    else:
        col_volume, col_top_customers = st.columns([1.35, 1])
        with col_volume:
            if period_mode == "Yearly":
                render_yearly_supplier_market_volume_chart(
                    df_channel,
                    **common_chart_kwargs,
                    supplier_color_map=supplier_colors,
                    empty_message="No yearly volume for this material type, sale channel, and supplier.",
                )
                year_customer_count_df = build_supplier_customer_new_current_data(
                    df_channel,
                    supplier=supplier,
                    material_type=material_type,
                    type_col=type_col,
                    supplier_col=supplier_col,
                    period_col="year",
                )
                render_supplier_customer_new_current_stacked_chart(
                    year_customer_count_df,
                    period_col="year",
                    title=(
                        f"New vs repeat customers · by year · "
                        f"{format_supplier_display_name(supplier)} · {material_type} · {sale_channel}"
                    ),
                    x_title="Year",
                    empty_message="No repeat or new-to-supplier customer data for these filters.",
                    chart_key="sup_year_customer_new_current",
                )
            elif period_mode == "Quarterly":
                render_quarterly_supplier_market_volume_chart(
                    df_channel,
                    **common_chart_kwargs,
                    year=year_int,
                    empty_message=f"No quarterly volume for {material_type} · {sale_channel}.",
                )
                quarter_customer_count_df = build_supplier_customer_new_current_data(
                    df_channel,
                    supplier=supplier,
                    material_type=material_type,
                    type_col=type_col,
                    supplier_col=supplier_col,
                    period_col="quarter",
                    year_int=year_int,
                )
                render_supplier_customer_new_current_stacked_chart(
                    quarter_customer_count_df,
                    period_col="quarter",
                    title=(
                        f"New vs repeat customers · by quarter · {year_int} · "
                        f"{format_supplier_display_name(supplier)} · {material_type} · {sale_channel}"
                    ),
                    x_title="Quarter",
                    empty_message="No repeat or new-to-supplier customer data for these filters.",
                    chart_key="sup_quarter_customer_new_current",
                )
                if selected_quarter:
                    quarter_scope = _filter_quarter_scope(top_customers_scope, selected_quarter)
                    render_supplier_period_customer_volume_chart(
                        quarter_scope,
                        supplier=supplier,
                        material_type=material_type,
                        sale_channel=sale_channel,
                        year_int=year_int,
                        period_label=str(selected_quarter).upper(),
                        top_n=top_customers_n,
                        chart_key=f"sup_quarter_customer_volume_{selected_quarter}_{year_int}",
                        empty_message="No customer volume for this supplier and quarter.",
                    )
            else:
                render_monthly_supplier_market_volume_chart(
                    df_channel,
                    **common_chart_kwargs,
                    year=year_int,
                    empty_message=f"No monthly volume for {material_type} · {sale_channel}.",
                )
                month_customer_count_df = build_supplier_customer_new_current_data(
                    df_channel,
                    supplier=supplier,
                    material_type=material_type,
                    type_col=type_col,
                    supplier_col=supplier_col,
                    period_col="month",
                    year_int=year_int,
                )
                render_supplier_customer_new_current_stacked_chart(
                    month_customer_count_df,
                    period_col="month",
                    title=(
                        f"New vs repeat customers · by month · {year_int} · "
                        f"{format_supplier_display_name(supplier)} · {material_type} · {sale_channel}"
                    ),
                    x_title="Month",
                    empty_message="No repeat or new-to-supplier customer data for these filters.",
                    chart_key="sup_month_customer_new_current",
                )
                if selected_month:
                    month_scope = _filter_month_scope(top_customers_scope, selected_month)
                    render_supplier_period_customer_volume_chart(
                        month_scope,
                        supplier=supplier,
                        material_type=material_type,
                        sale_channel=sale_channel,
                        year_int=year_int,
                        period_label=_month_display_label(selected_month),
                        top_n=top_customers_n,
                        chart_key=f"sup_month_customer_volume_{selected_month}_{year_int}",
                        empty_message="No customer volume for this supplier and month.",
                    )
        with col_top_customers:
            render_supplier_top_customers_chart(**top_customers_kwargs, side_panel=True)
            render_supplier_top_salers_chart(**top_salers_kwargs, side_panel=True)

    if st.session_state.get("show_detail_data", False) and not compare_mode:
        if period_scope.empty:
            st.warning("No shipment rows for the current filters.")
        else:
            render_styled_table(
                prepare_shipment_detail_table(period_scope),
                title="Shipment detail",
                subtitle=(
                    f"All import rows · {supplier} · {sale_channel} · {period_label} · {material_type}"
                ),
                export_filename="supplier_shipment_detail.csv",
            )
    else:
        st.info("Shipment detail is hidden. Enable **Show detail data** in the left sidebar.")
