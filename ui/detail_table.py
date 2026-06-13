"""Shared styled HTML tables for analysis tabs."""
from __future__ import annotations

import io

import pandas as pd
import streamlit as st

from config.settings import COL_BRAND_NAME, COL_SUPPLIER, COL_TYPE
from services.analysis_service import MONTH_ORDER

TABLE_COLUMNS = [
    "year",
    "month",
    "quarter",
    "date",
    COL_SUPPLIER,
    "supplier_raw",
    "supplier_group",
    COL_TYPE,
    "type_clean",
    COL_BRAND_NAME,
    "material",
    "customer_name",
    "Sale_chanel",
    "volume_ton",
    "total_usd",
    "unit_price",
    "country_origin",
    "hs_code",
    "description",
]

DETAIL_TABLE_SCROLL_HEIGHT_PX = 480

DETAIL_TABLE_HEADER_STYLES = [
    {
        "selector": "thead th",
        "props": [
            ("background", "linear-gradient(180deg, #0D9488 0%, #0F766E 100%)"),
            ("color", "#FFFFFF"),
            ("font-weight", "700"),
            ("font-size", "0.82rem"),
            ("text-align", "left"),
            ("padding", "10px 14px"),
            ("border", "none"),
            ("border-bottom", "2px solid #34D399"),
            ("white-space", "nowrap"),
        ],
    },
    {
        "selector": "tbody td",
        "props": [
            ("color", "#E5E7EB"),
            ("font-size", "0.8rem"),
            ("padding", "8px 14px"),
            ("border-bottom", "1px solid #2E343C"),
        ],
    },
    {
        "selector": "tbody tr:nth-child(even) td",
        "props": [("background-color", "#1A222C")],
    },
    {
        "selector": "tbody tr:nth-child(odd) td",
        "props": [("background-color", "#151A20")],
    },
    {
        "selector": "table",
        "props": [
            ("border-collapse", "collapse"),
            ("width", "max-content"),
            ("min-width", "100%"),
        ],
    },
]

DETAIL_DISPLAY_NAMES = {
    "year": "Year",
    "month": "Month",
    "quarter": "Quarter",
    "date": "Date",
    COL_SUPPLIER: "Supplier",
    COL_TYPE: "Material type",
    COL_BRAND_NAME: "Brand name",
    "material": "Material (display)",
    "customer_name": "Customer",
    "Sale_chanel": "Sale channel",
    "volume_ton": "Volume (ton)",
    "unit_price": "Unit price",
    "country_origin": "Origin",
    "hs_code": "HS code",
    "description": "Description",
}


def prepare_shipment_detail_table(filtered: pd.DataFrame) -> pd.DataFrame:
    excluded_cols = {"supplier_raw", "supplier_group", "type_clean", "total_usd"}
    show_cols = [c for c in TABLE_COLUMNS if c in filtered.columns and c not in excluded_cols]
    table = filtered[show_cols].copy()
    if "date" in table.columns:
        table["date"] = pd.to_datetime(table["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    if "volume_ton" in table.columns:
        table["volume_ton"] = pd.to_numeric(table["volume_ton"], errors="coerce").round(3)
    if "unit_price" in table.columns:
        table["unit_price"] = pd.to_numeric(table["unit_price"], errors="coerce").round(2)
    if "month" in table.columns:
        table["_ord"] = table["month"].astype(str).str.lower().map(MONTH_ORDER)
        table = table.sort_values("_ord").drop(columns="_ord")
    elif "date" in table.columns:
        table = table.sort_values("date")
    if "quarter" in table.columns:
        table["quarter"] = table["quarter"].astype(str).str.upper()
    if "month" in table.columns:
        table["month"] = table["month"].astype(str).str.title()
    rename_map = {k: v for k, v in DETAIL_DISPLAY_NAMES.items() if k in table.columns}
    return table.rename(columns=rename_map)


def style_table_html(table: pd.DataFrame) -> str:
    styler = table.style.set_table_styles(DETAIL_TABLE_HEADER_STYLES, overwrite=False).hide(axis="index")
    return styler.to_html()


def render_styled_table(
    table: pd.DataFrame,
    *,
    title: str,
    subtitle: str,
    export_filename: str = "detail_export.csv",
    max_height_px: int = DETAIL_TABLE_SCROLL_HEIGHT_PX,
    show_export: bool = True,
) -> None:
    st.markdown('<div class="detail-table-panel">', unsafe_allow_html=True)
    head_left, head_right = st.columns([2.2, 1])
    with head_left:
        st.markdown(
            (
                f'<div class="detail-table-title">{title}'
                f'<span class="detail-table-badge">{len(table):,} rows</span></div>'
                f'<div class="detail-table-subtitle">{subtitle}</div>'
            ),
            unsafe_allow_html=True,
        )
    with head_right:
        if show_export:
            csv_buf = io.StringIO()
            table.to_csv(csv_buf, index=False)
            st.download_button(
                "Export CSV",
                csv_buf.getvalue(),
                file_name=export_filename,
                mime="text/csv",
                use_container_width=True,
            )
    table_html = style_table_html(table)
    st.markdown(
        (
            f'<div class="detail-table-scroll-host" style="max-height:{max_height_px}px;">'
            f"{table_html}</div>"
        ),
        unsafe_allow_html=True,
    )
    st.caption("Scroll vertically and horizontally to view all rows and columns.")
    st.markdown("</div>", unsafe_allow_html=True)


def render_customer_summary_table(detail: dict) -> None:
    """Single-row summary after selecting a customer on the bar chart."""
    table = pd.DataFrame(
        [
            {
                "Customer name": detail.get("customer_name", "—"),
                "Volume (ton)": round(float(detail.get("volume_ton", 0)), 3),
                "Share (%)": float(detail.get("share_pct", 0)),
            }
        ]
    )
    render_styled_table(
        table,
        title="Customer detail",
        subtitle="Selected customer · volume and share of supplier sales in this period",
        export_filename="customer_detail.csv",
        max_height_px=120,
        show_export=False,
    )
