"""Tab 3 — Customer deep dive: import volume, supplier mix, and customer comparison."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from config.settings import SALE_CHANNEL_FILTER_OPTIONS
from services.analysis_service import MONTH_ORDER, filter_by_material_type, filter_options, resolve_type_column
from services.customer_filter_service import (
    customer_id_to_name,
    filter_by_customer,
    prepare_customer_analysis_frame,
    resolve_customer_col,
    resolve_customer_filter_options,
)
from ui.chart_volume import (
    MONTH_DISPLAY,
    render_customer_compare_dashboard,
    render_customer_period_supplier_volume_chart,
    render_customer_supplier_mix_chart,
    render_monthly_customer_market_volume_chart,
    render_quarterly_customer_market_volume_chart,
    render_yearly_customer_market_volume_chart,
)
from ui.detail_table import prepare_shipment_detail_table, render_styled_table
from ui.sidebar_analysis import (
    ANALYSIS_FILTER_CUSTOMER,
    ANALYSIS_FILTER_MTYPE,
    ANALYSIS_FILTER_YEAR,
    get_analysis_subtab_label,
)
from ui.theme import (
    dashboard_header,
    format_customer_display_name,
    format_customer_import_kpi_label,
    format_customer_suppliers_kpi_label,
    format_supplier_display_name,
    kpi_card,
    render_customer_analysis_chip_row,
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


def _top_suppliers_table(filtered: pd.DataFrame, supplier_col: str) -> pd.DataFrame:
    if filtered.empty or supplier_col not in filtered.columns:
        return pd.DataFrame(columns=["supplier", "volume_ton", "share_pct"])

    work = filtered.copy()
    work[supplier_col] = work[supplier_col].fillna("Unknown supplier").astype(str).str.strip()
    work = work[work[supplier_col] != ""]
    grouped = (
        work.groupby(supplier_col, dropna=False)["volume_ton"]
        .sum()
        .reset_index()
        .sort_values("volume_ton", ascending=False)
    )
    grouped = grouped.rename(columns={supplier_col: "supplier"})
    total = float(grouped["volume_ton"].sum())
    grouped["share_pct"] = (
        (grouped["volume_ton"] / total * 100).round(1) if total > 0 else 0.0
    )
    return grouped


def _render_period_controls(
    *,
    year: str,
    year_customer_scope: pd.DataFrame,
) -> tuple[str, str, str | None, str | None]:
    """Period + optional quarter/month sub-select."""
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
            key="cust_period_mode",
        )
    selected_quarter: str | None = None
    selected_month: str | None = None
    if period_mode == "Quarterly":
        available = _quarters_with_data(year_customer_scope)
        with col_sub:
            if available:
                current = st.session_state.get("cust_quarter_select")
                if current not in available:
                    st.session_state["cust_quarter_select"] = available[-1]
                selected_quarter = st.selectbox(
                    "Quarter",
                    available,
                    format_func=lambda q: str(q).upper(),
                    key="cust_quarter_select",
                )
            else:
                st.selectbox("Quarter", ["—"], disabled=True, key="cust_quarter_select_empty")
    elif period_mode == "Monthly":
        available = _months_with_data(year_customer_scope)
        with col_sub:
            if available:
                current = st.session_state.get("cust_month_select")
                if current not in available:
                    st.session_state["cust_month_select"] = available[-1]
                selected_month = st.selectbox(
                    "Month",
                    available,
                    format_func=_month_display_label,
                    key="cust_month_select",
                )
            else:
                st.selectbox("Month", ["—"], disabled=True, key="cust_month_select_empty")
    return period_mode, f"Full year {year}", selected_quarter, selected_month


def _month_display_label(month_key: str) -> str:
    m = str(month_key).strip().lower()
    num = MONTH_ORDER.get(m)
    if num and 1 <= num <= 12:
        return MONTH_DISPLAY[num - 1]
    return str(month_key).upper()


def _months_with_data(df: pd.DataFrame) -> list[str]:
    if df.empty or "month" not in df.columns:
        return []
    present = {
        str(m).strip().lower()
        for m in df["month"].dropna().unique()
        if str(m).strip()
    }
    return sorted(present, key=lambda m: MONTH_ORDER.get(m, 99))


def _quarters_with_data(df: pd.DataFrame) -> list[str]:
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


def _filter_month_scope(df: pd.DataFrame, month: str) -> pd.DataFrame:
    if df.empty or "month" not in df.columns:
        return df.iloc[0:0].copy()
    m = str(month).strip().lower()
    mask = df["month"].astype(str).str.strip().str.lower() == m
    return df.loc[mask].copy()


def _render_view_mode_controls(
    customer_ids: list[str],
    id_to_name: dict[str, str],
    primary_customer_id: str,
) -> tuple[str, list[str]]:
    view_mode = st.radio(
        "View",
        ["Single customer", "Compare customers"],
        horizontal=True,
        key="cust_view_mode",
    )
    compare_customers: list[str] = []
    if view_mode == "Compare customers":
        defaults: list[str] = []
        if primary_customer_id in customer_ids:
            defaults.append(primary_customer_id)
        for cid in customer_ids:
            if cid not in defaults:
                defaults.append(cid)
            if len(defaults) >= 2:
                break
        compare_customers = st.multiselect(
            "Customers to compare (2–5)",
            customer_ids,
            default=defaults[: min(2, len(defaults))],
            format_func=lambda cid: format_customer_display_name(id_to_name.get(cid, cid)),
            key="cust_compare_customers",
        )
        compare_customers = compare_customers[:5]
        if len(compare_customers) < 2:
            st.info("Select at least **2 customers** to compare volume and market share.")
    return view_mode, compare_customers


def render_customer_page(df: pd.DataFrame, dataset_label: str) -> None:
    df = _ensure_quarter_column(df)
    opts = filter_options(df)

    years = opts.get("years", [])
    supplier_col = "supplier_raw" if "supplier_raw" in df.columns else "supplier_group"
    customer_col = resolve_customer_col(df)
    types = [
        t
        for t in opts.get("material_types", [])
        if str(t).strip() and str(t).lower() not in ("unspecified", "nan")
    ]

    if not years:
        st.warning("No year column found in the file.")
        return
    if customer_col not in df.columns and "customer_name" not in df.columns:
        st.warning("No customer column found in the file.")
        return
    if not types and "type_clean" in df.columns:
        types = sorted(df["type_clean"].dropna().unique().tolist(), key=str)

    sale_channel = st.session_state.get(
        "analysis_sale_channel",
        SALE_CHANNEL_FILTER_OPTIONS[0],
    )

    material_type = st.session_state.get(ANALYSIS_FILTER_MTYPE)
    if not material_type or material_type not in types:
        from ui.sidebar_analysis import _default_material_type_for_dataset

        material_type = _default_material_type_for_dataset(types) if types else ""

    year = st.session_state.get(ANALYSIS_FILTER_YEAR, years[-1] if years else "")
    if year not in years:
        year = years[-1] if years else year
    year_int = int(year)

    customer_id = st.session_state.get(ANALYSIS_FILTER_CUSTOMER, "")
    customer_options = resolve_customer_filter_options(
        df,
        material_type=material_type,
        sale_channel=sale_channel,
        year=year_int,
    )
    if not customer_options:
        st.warning("No customers match the current dataset, material type, and sale channel filters.")
        return

    customer_ids = [cid for cid, _ in customer_options]
    id_to_name = customer_id_to_name(customer_options)
    if customer_id not in customer_ids:
        customer_id = customer_ids[0]
    customer_name = id_to_name.get(customer_id, customer_id)

    dashboard_header(
        get_analysis_subtab_label(),
        f"Vietnam Chemical Import Intelligence · {dataset_label}",
    )
    if st.session_state.get("dashboard_msg"):
        st.success(st.session_state.dashboard_msg)

    render_customer_analysis_chip_row(
        dataset_label=dataset_label,
        sale_channel=sale_channel,
        sale_channel_options=SALE_CHANNEL_FILTER_OPTIONS,
        year=year,
        customer_name=customer_name,
        show_customer=st.session_state.get("cust_view_mode", "Single customer") != "Compare customers",
    )

    type_col = resolve_type_column(df)
    df_channel = prepare_customer_analysis_frame(
        df,
        dataset_label=dataset_label,
        material_type=material_type,
        sale_channel=sale_channel,
        type_col=type_col,
        supplier_col=supplier_col,
    )

    year_df = df_channel[df_channel["year"] == year_int] if "year" in df_channel.columns else df_channel
    year_scope = filter_by_material_type(
        filter_by_customer(year_df, customer_id, customer_col=customer_col),
        material_type,
        type_col=type_col,
    )

    period_mode, period_label, selected_quarter, selected_month = _render_period_controls(
        year=year,
        year_customer_scope=year_scope,
    )
    view_mode, compare_customers = _render_view_mode_controls(
        customer_ids, id_to_name, customer_id
    )
    compare_mode = view_mode == "Compare customers" and len(compare_customers) >= 2

    suppliers_all = _top_suppliers_table(year_scope, supplier_col)
    total_ton = float(year_scope["volume_ton"].sum()) if not year_scope.empty else 0.0
    n_suppliers = len(suppliers_all)
    top_row = suppliers_all.iloc[0] if not suppliers_all.empty else None
    top_pct = float(top_row["share_pct"]) if top_row is not None else 0.0
    top_supplier = (
        format_supplier_display_name(str(top_row["supplier"])) if top_row is not None else "—"
    )

    if not compare_mode:
        m1, m2, m3 = st.columns(3)
        with m1:
            kpi_label = format_customer_import_kpi_label(
                customer_name=customer_name,
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
                f"{n_suppliers:,}",
                format_customer_suppliers_kpi_label(year=year),
                "◎",
                icon_class="blue",
            )
        with m3:
            kpi_card(
                f"{top_pct:.1f}%",
                f"Largest supplier · {top_supplier[:28]}",
                "◈",
                icon_class="gray",
            )

    common_chart_kwargs = dict(
        material_type=material_type,
        customer_id=customer_id,
        customer_name=customer_name,
        type_col=type_col,
        customer_col=customer_col,
    )

    mix_kwargs = dict(
        material_type=material_type,
        customer_id=customer_id,
        customer_name=customer_name,
        type_col=type_col,
        customer_col=customer_col,
        supplier_col=supplier_col,
        year=year_int,
        sale_channel=sale_channel,
    )

    mix_source = filter_by_material_type(
        filter_by_customer(year_df, customer_id, customer_col=customer_col),
        material_type,
        type_col=type_col,
    )

    if compare_mode:
        render_customer_compare_dashboard(
            df_channel,
            material_type=material_type,
            customer_ids=compare_customers,
            id_to_name=id_to_name,
            type_col=type_col,
            customer_col=customer_col,
            period_mode=period_mode,
            year_int=year_int,
            sale_channel=sale_channel,
        )
    else:
        col_volume, col_suppliers = st.columns([1.35, 1])
        with col_volume:
            if period_mode == "Yearly":
                render_yearly_customer_market_volume_chart(
                    df_channel,
                    **common_chart_kwargs,
                    empty_message="No yearly volume for this material type, sale channel, and customer.",
                )
            elif period_mode == "Quarterly":
                render_quarterly_customer_market_volume_chart(
                    df_channel,
                    **common_chart_kwargs,
                    year=year_int,
                    empty_message=f"No quarterly volume for {material_type} · {sale_channel}.",
                )
                if selected_quarter:
                    quarter_scope = _filter_quarter_scope(year_scope, selected_quarter)
                    render_customer_period_supplier_volume_chart(
                        quarter_scope,
                        customer_name=customer_name,
                        material_type=material_type,
                        sale_channel=sale_channel,
                        year_int=year_int,
                        period_label=str(selected_quarter).upper(),
                        supplier_col=supplier_col,
                        chart_key=f"cust_quarter_supplier_volume_{selected_quarter}_{year_int}",
                        empty_message="No supplier volume for this customer and quarter.",
                    )
            else:
                render_monthly_customer_market_volume_chart(
                    df_channel,
                    **common_chart_kwargs,
                    year=year_int,
                    empty_message=f"No monthly volume for {material_type} · {sale_channel}.",
                )
                if selected_month:
                    month_scope = _filter_month_scope(year_scope, selected_month)
                    render_customer_period_supplier_volume_chart(
                        month_scope,
                        customer_name=customer_name,
                        material_type=material_type,
                        sale_channel=sale_channel,
                        year_int=year_int,
                        period_label=_month_display_label(selected_month),
                        supplier_col=supplier_col,
                        chart_key=f"cust_month_supplier_volume_{selected_month}_{year_int}",
                        empty_message="No supplier volume for this customer and month.",
                    )
        with col_suppliers:
            render_customer_supplier_mix_chart(
                mix_source,
                **mix_kwargs,
                side_panel=True,
            )

    if st.session_state.get("show_detail_data", False) and not compare_mode:
        if year_scope.empty:
            st.warning("No shipment rows for the current filters.")
        else:
            render_styled_table(
                prepare_shipment_detail_table(year_scope),
                title="Shipment detail",
                subtitle=(
                    f"All import rows · {format_customer_display_name(customer_name)} · "
                    f"{sale_channel} · {period_label} · {material_type}"
                ),
                export_filename="customer_shipment_detail.csv",
            )
    elif not compare_mode:
        st.info("Shipment detail is hidden. Enable **Show detail data** in the left sidebar.")
