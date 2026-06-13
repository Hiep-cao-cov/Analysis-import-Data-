"""Tab 1 — Market overview (existing dashboard UI)."""

from __future__ import annotations



import pandas as pd

import streamlit as st



from config.settings import SALE_CHANNEL_FILTER_OPTIONS

from services.analysis_service import filter_by_material_type, filter_options, resolve_type_column
from services.supplier_filter_service import (
    prepare_supplier_analysis_frame,
    resolve_supplier_filter_options,
)

from ui.chart_volume import (
    render_monthly_deep_dive_chart,
    render_monthly_deep_dive_supplier_chart,
    render_yearly_volume_market_share_chart,
    supplier_color_map_for_material,
)

from ui.detail_table import prepare_shipment_detail_table, render_styled_table

from ui.sidebar_analysis import get_analysis_subtab_label

from ui.theme import (
    chart_card_title,
    dashboard_header,
    format_market_total_kpi_label,
    format_supplier_display_name,
    format_supplier_sale_kpi_label,
    format_supplier_share_kpi_label,
    kpi_card,
    render_analysis_chip_row,
)




def _supplier_share_same_material(

    df: pd.DataFrame,

    year: int,

    material_type: str,

    selected_supplier: str,

    supplier_col: str,

) -> tuple[pd.DataFrame, float, float]:

    type_col = resolve_type_column(df)

    base = filter_by_material_type(df, material_type, type_col=type_col)
    base = base[base["year"] == year]

    if base.empty:

        return pd.DataFrame(), 0.0, 0.0



    by_supplier = (

        base.groupby(supplier_col, dropna=False)["volume_ton"]

        .sum()

        .reset_index()

        .sort_values("volume_ton", ascending=False)

    )

    market_ton = float(by_supplier["volume_ton"].sum())

    row = by_supplier[by_supplier[supplier_col] == selected_supplier]

    supplier_ton = float(row["volume_ton"].sum()) if not row.empty else 0.0



    pie_df = by_supplier.rename(columns={supplier_col: "supplier", "volume_ton": "volume_ton"})

    pie_df["share_pct"] = (pie_df["volume_ton"] / market_ton * 100).round(1) if market_ton else 0.0

    return pie_df, supplier_ton, market_ton





def _share_pie_chart(
    pie_df: pd.DataFrame,
    selected_supplier: str,
    material_type: str,
    year: int,
    supplier_color_map: dict[str, str],
):

    if pie_df.empty:

        st.info("No market data for this material type.")

        return



    import plotly.express as px



    pie_display = pie_df.copy()
    pie_display["supplier"] = pie_display["supplier"].map(format_supplier_display_name)
    display_color_map = {
        format_supplier_display_name(name): color
        for name, color in supplier_color_map.items()
    }
    selected_display = format_supplier_display_name(selected_supplier)

    fig = px.pie(
        pie_display,
        names="supplier",
        values="volume_ton",
        color="supplier",
        color_discrete_map=display_color_map,
        title=None,
        hole=0.4,
    )

    fig.update_traces(
        textposition="inside",
        textinfo="percent+label",
        pull=[0.08 if s == selected_display else 0 for s in pie_display["supplier"]],
    )

    fig.update_layout(

        height=400,

        margin=dict(l=10, r=10, t=12, b=10),

        paper_bgcolor="rgba(0,0,0,0)",

        plot_bgcolor="rgba(0,0,0,0)",

        font=dict(color="#E5E7EB"),

        legend=dict(font=dict(color="#F9FAFB", size=12)),

    )

    st.plotly_chart(fig, use_container_width=True)





def render_market_page(df: pd.DataFrame, dataset_label: str) -> None:

    opts = filter_options(df)



    years = opts.get("years", [])

    supplier_col = "supplier_raw" if "supplier_raw" in df.columns else "supplier_group"

    types = [t for t in opts.get("material_types", []) if str(t).strip() and str(t).lower() not in ("unspecified", "nan")]

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

    year = st.session_state.get(ANALYSIS_FILTER_YEAR, years[-1] if years else "")
    supplier = st.session_state.get(ANALYSIS_FILTER_SUPPLIER, suppliers[0] if suppliers else "")
    if year not in years:
        year = years[-1] if years else year
    if supplier not in suppliers:
        supplier = suppliers[0] if suppliers else supplier

    dashboard_header(
        get_analysis_subtab_label(),
        f"Vietnam Chemical Import Intelligence · {dataset_label}",
    )

    if st.session_state.get("dashboard_msg"):
        st.success(st.session_state.dashboard_msg)

    render_analysis_chip_row(
        dataset_label=dataset_label,
        sale_channel=sale_channel,
        sale_channel_options=SALE_CHANNEL_FILTER_OPTIONS,
        year=year,
        supplier=supplier,
    )

    year_int = int(year)

    df_channel = prepare_supplier_analysis_frame(
        df,
        dataset_label=dataset_label,
        material_type=material_type,
        sale_channel=sale_channel,
        supplier_col=supplier_col,
    )
    type_col = resolve_type_column(df_channel)

    filtered = filter_by_material_type(
        df_channel[(df_channel["year"] == year_int) & (df_channel[supplier_col] == supplier)],
        material_type,
        type_col=type_col,
    )



    pie_df, supplier_ton, market_ton = _supplier_share_same_material(

        df_channel, year_int, material_type, supplier, supplier_col=supplier_col

    )

    share_pct = (supplier_ton / market_ton * 100) if market_ton > 0 else 0.0

    supplier_colors = supplier_color_map_for_material(
        df_channel,
        material_type=material_type,
        type_col=type_col,
        supplier_col=supplier_col,
    )

    m1, m2, m3 = st.columns(3)

    with m1:

        kpi_card(
            f"{supplier_ton:,.1f}",
            format_supplier_sale_kpi_label(
                supplier=supplier,
                material_type=material_type,
                year=year_int,
                sale_channel=sale_channel,
            ),
            "◉",
            icon_class="green",
            label_variant="green-lg",
        )

    with m2:

        kpi_card(
            f"{market_ton:,.1f}",
            format_market_total_kpi_label(
                material_type=material_type,
                year=year_int,
                sale_channel=sale_channel,
            ),
            "$",
            icon_class="blue",
            label_variant="yellow-lg",
        )

    with m3:

        kpi_card(
            f"{share_pct:.1f}%",
            format_supplier_share_kpi_label(
                supplier=supplier,
                material_type=material_type,
                year=year_int,
                sale_channel=sale_channel,
            ),
            "◈",
            icon_class="blue",
            label_variant="blue-lg",
        )



    col_bar, col_pie = st.columns([1.2, 1])

    with col_bar:

        render_yearly_volume_market_share_chart(

            df_channel,

            material_type=material_type,

            selected_supplier=supplier,

            type_col=type_col,

            supplier_col=supplier_col,

            supplier_color_map=supplier_colors,

            empty_message="No yearly volume for this material type and sale channel.",

        )

    with col_pie:

        chart_card_title(f"Supplier market share ({year_int}) · {material_type}", large=True)

        _share_pie_chart(pie_df, supplier, material_type, year_int, supplier_colors)

    md_all, md_sup = st.columns(2)
    with md_all:
        render_monthly_deep_dive_chart(
            df_channel,
            material_type=material_type,
            type_col=type_col,
            empty_message=f"No monthly market volume for {material_type} in this dataset.",
        )
    with md_sup:
        render_monthly_deep_dive_supplier_chart(
            df_channel,
            material_type=material_type,
            selected_supplier=supplier,
            type_col=type_col,
            supplier_col=supplier_col,
            empty_message=f"No monthly volume for {supplier} and {material_type}.",
        )

    info_left, info_right = st.columns([1.25, 1])

    with info_left:

        chart_card_title(f"Top customers ({year_int})")

        if "customer_name" not in filtered.columns or filtered.empty:

            st.markdown('<div class="event-row">No customer volume data for current filters.</div>', unsafe_allow_html=True)

        else:

            customer_df = filtered.copy()

            customer_df["customer_name"] = customer_df["customer_name"].fillna("Unknown customer").astype(str).str.strip()

            customer_df = customer_df[customer_df["customer_name"] != ""]

            top_customers = (

                customer_df.groupby("customer_name", dropna=False)["volume_ton"]

                .sum()

                .reset_index()

                .sort_values("volume_ton", ascending=False)

                .head(7)

            )

            total_customer_volume = float(top_customers["volume_ton"].sum()) if not top_customers.empty else 0.0

            if top_customers.empty or total_customer_volume <= 0:

                st.markdown('<div class="event-row">No customer volume data for current filters.</div>', unsafe_allow_html=True)

            else:

                for _, row in top_customers.iterrows():

                    customer_name = str(row["customer_name"])

                    volume = float(row["volume_ton"])

                    pct = volume / total_customer_volume * 100

                    st.markdown(

                        (

                            '<div class="supplier-row">'

                            f'<div class="label"><span>{customer_name}</span><span>{volume:,.1f} ton · {pct:.1f}%</span></div>'

                            f'<div class="bar"><span style="width:{pct:.1f}%"></span></div>'

                            "</div>"

                        ),

                        unsafe_allow_html=True,

                    )



    with info_right:

        chart_card_title(f"Top suppliers ({year_int})")

        top_sup = pie_df.sort_values("volume_ton", ascending=False).head(7) if not pie_df.empty else pd.DataFrame()

        if top_sup.empty:

            st.markdown('<div class="event-row">No supplier share data.</div>', unsafe_allow_html=True)

        else:

            for _, row in top_sup.iterrows():

                sup_name = str(row["supplier"])

                pct = float(row.get("share_pct", 0.0))

                st.markdown(

                    (

                        '<div class="supplier-row">'

                        f'<div class="label"><span>{sup_name}</span><span>{pct:.1f}%</span></div>'

                        f'<div class="bar"><span style="width:{pct:.1f}%"></span></div>'

                        "</div>"

                    ),

                    unsafe_allow_html=True,

                )



    if st.session_state.get("show_detail_data", False):

        if filtered.empty:

            st.warning("No rows for the selected year, supplier, and material type.")

        else:

            render_styled_table(

                prepare_shipment_detail_table(filtered),

                title="Shipment detail",

                subtitle="Filtered records for your selected year, supplier, and material",

                export_filename="shipment_detail.csv",

            )

    else:

        st.info("Detail data is hidden. Enable 'Show detail data' in the left sidebar.")


