"""Shared volume charts for Market overview and Supplier deep dive."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from config.settings import (
    CUSTOMER_COMPARE_FALLBACK_COLORS,
    SUPPLIER_COMPARE_BAR_COLORS,
    SUPPLIER_COMPARE_FALLBACK_COLORS,
)
from services.analysis_service import (
    MONTH_ORDER,
    QUARTER_ORDER,
    filter_by_material_type,
)
from services.customer_name_service import normalize_customer_id
from services.supplier_filter_service import supplier_filter_key
from ui.theme import (
    CHART,
    chart_card_title,
    chart_footnote,
    format_customer_display_name,
    format_saler_display_name,
    format_supplier_display_name,
)


def format_dataset_year_range(df: pd.DataFrame) -> str:
    """Year span in dataset for chart titles, e.g. '(2022 - 2026)'."""
    if df.empty or "year" not in df.columns:
        return ""
    years = sorted(
        pd.to_numeric(df["year"], errors="coerce").dropna().astype(int).unique().tolist()
    )
    if not years:
        return ""
    if len(years) == 1:
        return f"({years[0]})"
    return f"({years[0]} - {years[-1]})"


SUPPLIER_CHART_PALETTE = CHART["pie"] + [
    CHART["purple"],
    CHART["yellow"],
    CHART["gray"],
    "#F472B6",
    "#22D3EE",
    "#84CC16",
]

YEARLY_STACK_BAR_HOVERLABEL = dict(
    bgcolor="#000000",
    bordercolor="#FACC15",
    font=dict(color="#FACC15", size=14, family="Arial"),
)
YEARLY_SHARE_LINE_HOVERLABEL = dict(
    bgcolor="#1E3A5F",
    bordercolor="#2563EB",
    font=dict(color="#FACC15", size=14, family="Arial"),
)
PERIOD_CUSTOMER_VOLUME_HOVERLABEL = dict(
    bgcolor="#1E3A5F",
    bordercolor="#2563EB",
    font=dict(color="#FACC15", size=14, family="Segoe UI"),
)
# Ranked customer bars (Q/M period chart): dark → light blue by rank
CUSTOMER_RANK_BAR_BLUES = ["#1D4ED8", "#2563EB", "#3B82F6", "#60A5FA", "#93C5FD", "#BFDBFE"]
CUSTOMER_RANK_OTHERS_COLOR = "#4B5563"


def supplier_color_map_for_material(
    df: pd.DataFrame,
    *,
    material_type: str,
    type_col: str,
    supplier_col: str,
) -> dict[str, str]:
    """
    Stable supplier → color mapping from total volume (all years) for one material.
    Same supplier always gets the same color across stacked bar and pie charts.
    """
    if df.empty or supplier_col not in df.columns:
        return {}
    base = filter_by_material_type(df, material_type, type_col=type_col)
    if base.empty:
        return {}
    vol = (
        base.groupby(supplier_col, dropna=False)["volume_ton"]
        .sum()
        .sort_values(ascending=False)
    )
    ordered = [str(s) for s in vol.index.tolist()]
    return {
        name: SUPPLIER_CHART_PALETTE[i % len(SUPPLIER_CHART_PALETTE)]
        for i, name in enumerate(ordered)
    }


def _supplier_color(color_map: dict[str, str], supplier: str) -> str:
    key = str(supplier)
    if key in color_map:
        return color_map[key]
    key_upper = key.strip().upper()
    for map_key, color in color_map.items():
        if str(map_key).strip().upper() == key_upper:
            return color
    idx = len(color_map) % len(SUPPLIER_CHART_PALETTE)
    return SUPPLIER_CHART_PALETTE[idx]


def build_supplier_compare_color_map(suppliers: list[str]) -> dict[str, str]:
    """Fixed bar colors for Compare suppliers volume chart."""
    used_colors = set(SUPPLIER_COMPARE_BAR_COLORS.values())
    fallbacks = [c for c in SUPPLIER_COMPARE_FALLBACK_COLORS if c not in used_colors]
    result: dict[str, str] = {}
    fallback_idx = 0

    for sup in suppliers:
        mapped = SUPPLIER_COMPARE_BAR_COLORS.get(supplier_filter_key(sup))
        if mapped:
            result[str(sup)] = mapped
            continue

        color: str | None = None
        while fallback_idx < len(fallbacks):
            candidate = fallbacks[fallback_idx]
            fallback_idx += 1
            if candidate not in used_colors:
                color = candidate
                used_colors.add(candidate)
                break
        if color is None:
            color = SUPPLIER_CHART_PALETTE[fallback_idx % len(SUPPLIER_CHART_PALETTE)]
            fallback_idx += 1
        result[str(sup)] = color

    return result


def order_months(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "month" not in df.columns:
        return df
    out = df.copy()
    out["_ord"] = out["month"].astype(str).str.lower().map(MONTH_ORDER)
    return out.sort_values("_ord").drop(columns="_ord")


def monthly_volume_ton(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["month", "volume_ton"])
    g = df.groupby("month", dropna=False)["volume_ton"].sum().reset_index()
    return order_months(g)


def order_quarters(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "quarter" not in df.columns:
        return df
    out = df.copy()
    out["quarter"] = out["quarter"].astype(str).str.strip().str.lower()
    out["_ord"] = out["quarter"].map(QUARTER_ORDER)
    return out.sort_values("_ord").drop(columns="_ord")


def quarterly_volume_ton(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["quarter", "volume_ton"])
    work = df.copy()
    if "quarter" not in work.columns and "month" in work.columns:
        month_to_q = {
            "jan": "q1", "feb": "q1", "mar": "q1",
            "apr": "q2", "may": "q2", "jun": "q2",
            "jul": "q3", "aug": "q3", "sep": "q3",
            "oct": "q4", "nov": "q4", "dec": "q4",
        }
        work["quarter"] = work["month"].astype(str).str.lower().map(month_to_q)
    if "quarter" not in work.columns:
        return pd.DataFrame(columns=["quarter", "volume_ton"])
    work["quarter"] = work["quarter"].astype(str).str.strip().str.lower()
    g = work.groupby("quarter", dropna=False)["volume_ton"].sum().reset_index()
    return order_quarters(g)


def render_volume_period_bar_chart(
    period_df: pd.DataFrame,
    *,
    period_col: str,
    x_label: str,
    empty_message: str,
    title: str = "Import volume trend",
) -> None:
    chart_card_title(title)
    if period_df.empty:
        st.info(empty_message)
        return

    import plotly.express as px

    chart_df = period_df.copy()
    chart_df["period_label"] = chart_df[period_col].astype(str).str.upper()

    fig = px.bar(
        chart_df,
        x="period_label",
        y="volume_ton",
        title=None,
        labels={"period_label": x_label, "volume_ton": "Volume (ton)"},
        color_discrete_sequence=[CHART["green"]],
        template="plotly_dark",
    )
    fig.update_layout(
        height=400,
        margin=dict(l=20, r=20, t=44, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(categoryorder="array", categoryarray=chart_df["period_label"].tolist()),
        font=dict(color="#E5E7EB"),
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(title="Volume (ton)", gridcolor="#374151")
    st.plotly_chart(fig, use_container_width=True)


def build_yearly_top5_share_data(
    df: pd.DataFrame,
    *,
    material_type: str,
    selected_supplier: str,
    type_col: str,
    supplier_col: str,
    top_n: int = 5,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Returns (stack_df, share_df).
    stack_df: year, supplier, volume_ton for top N suppliers per year.
    share_df: year, share_pct, supplier_ton, market_ton (full market per year).
    stack_df: top N suppliers per year plus an Others segment for the remainder.
    """
    if df.empty or "year" not in df.columns:
        return pd.DataFrame(), pd.DataFrame()

    mt = str(material_type).strip()
    base = filter_by_material_type(df, mt, type_col=type_col)
    if base.empty:
        return pd.DataFrame(), pd.DataFrame()

    base["year"] = pd.to_numeric(base["year"], errors="coerce")
    base = base.dropna(subset=["year"])
    base["year"] = base["year"].astype(int)
    years = sorted(base["year"].unique().tolist())
    stack_rows: list[dict] = []
    share_rows: list[dict] = []

    for year in years:
        year_df = base[base["year"] == year]
        by_supplier = (
            year_df.groupby(supplier_col, dropna=False)["volume_ton"]
            .sum()
            .reset_index()
            .sort_values("volume_ton", ascending=False)
        )
        market_ton = float(year_df["volume_ton"].sum())
        supplier_ton = _supplier_volume_in_year(year_df, supplier_col, selected_supplier)
        share_pct = (supplier_ton / market_ton * 100) if market_ton > 0 else 0.0
        share_rows.append(
            {
                "year": year,
                "share_pct": round(share_pct, 1),
                "supplier_ton": supplier_ton,
                "market_ton": market_ton,
            }
        )

        top = by_supplier.head(top_n)
        top_sum = float(top["volume_ton"].sum()) if not top.empty else 0.0
        for _, row in top.iterrows():
            stack_rows.append({
                "year": year,
                "supplier": str(row[supplier_col]),
                "volume_ton": float(row["volume_ton"]),
            })
        others_ton = max(market_ton - top_sum, 0.0)
        if others_ton > 0:
            stack_rows.append({
                "year": year,
                "supplier": TOP5_OTHERS_LABEL,
                "volume_ton": others_ton,
            })

    stack_df = pd.DataFrame(stack_rows)
    share_df = pd.DataFrame(share_rows)
    return stack_df, share_df


OTHER_SUPPLIERS_LABEL = "Other suppliers"
TOP5_OTHERS_LABEL = "Others"


def _selected_supplier_ton(
    by_supplier: pd.DataFrame,
    supplier_col: str,
    selected_supplier: str,
) -> float:
    """Match sidebar supplier name to grouped volume (string-safe)."""
    if by_supplier.empty:
        return 0.0
    sel = str(selected_supplier).strip()
    names = by_supplier[supplier_col].astype(str).str.strip()
    row = by_supplier[names == sel]
    if row.empty:
        row = by_supplier[names.str.casefold() == sel.casefold()]
    return float(row["volume_ton"].sum()) if not row.empty else 0.0


def _supplier_volume_in_year(
    year_df: pd.DataFrame,
    supplier_col: str,
    selected_supplier: str,
) -> float:
    """Sum volume_ton for the selected supplier in one material-year slice."""
    if year_df.empty or supplier_col not in year_df.columns:
        return 0.0
    sel = str(selected_supplier).strip().casefold()
    mask = year_df[supplier_col].astype(str).str.strip().str.casefold() == sel
    return float(year_df.loc[mask, "volume_ton"].sum())


def _selected_supplier_bar_color(color_map: dict[str, str], supplier_name: str) -> str:
    """Avoid gray-on-gray: selected supplier must contrast with Other suppliers."""
    color = _supplier_color(color_map, supplier_name)
    if str(color).upper() in ("#9CA3AF", CHART["gray"].upper()):
        return CHART["green"]
    return color


def _build_period_supplier_vs_market_data(
    df: pd.DataFrame,
    *,
    material_type: str,
    selected_supplier: str,
    type_col: str,
    supplier_col: str,
    period_col: str,
    period_order: dict[str, int],
) -> pd.DataFrame:
    """
    Generic builder: one row per period value (year / quarter / month).
    Returns columns: period, supplier_ton, other_ton, market_ton, share_pct.
    """
    if df.empty or period_col not in df.columns or "volume_ton" not in df.columns:
        return pd.DataFrame()
    mt = str(material_type).strip()
    base = filter_by_material_type(df, mt, type_col=type_col)
    if base.empty:
        return pd.DataFrame()
    base[period_col] = base[period_col].astype(str).str.strip().str.lower()
    periods = sorted(base[period_col].dropna().unique().tolist(),
                     key=lambda p: period_order.get(p, 99))
    rows: list[dict] = []
    for period in periods:
        period_df = base[base[period_col] == period]
        market_ton = float(period_df["volume_ton"].sum())
        sel = str(selected_supplier).strip().casefold()
        mask = period_df[supplier_col].astype(str).str.strip().str.casefold() == sel
        supplier_ton = float(period_df.loc[mask, "volume_ton"].sum())
        other_ton = max(market_ton - supplier_ton, 0.0)
        share_pct = (supplier_ton / market_ton * 100) if market_ton > 0 else 0.0
        rows.append({
            "period": period,
            "supplier_ton": supplier_ton,
            "other_ton": other_ton,
            "market_ton": market_ton,
            "share_pct": round(share_pct, 1),
        })
    return pd.DataFrame(rows)


def _render_supplier_market_stacked_chart(
    period_df: pd.DataFrame,
    *,
    period_labels: list[str],
    title: str,
    supplier_name: str,
    supplier_legend: str,
    market_legend: str,
    share_legend: str,
    chart_key: str,
    x_title: str = "",
    empty_message: str = "No data.",
) -> None:
    """Shared rendering logic for yearly/quarterly/monthly supplier-vs-market stacked bar."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    chart_card_title(title, large=True)
    if period_df.empty:
        st.info(empty_message)
        return

    supplier_vol = period_df["supplier_ton"].astype(float).tolist()
    other_vol    = period_df["other_ton"].astype(float).tolist()
    market_vol   = period_df["market_ton"].astype(float).tolist()
    share_vol    = period_df["share_pct"].astype(float).tolist()

    if not any(v > 0 for v in supplier_vol):
        st.warning(f"No import volume found for **{supplier_name}** in this material and sale channel.")

    supplier_bar_color  = "#1D4ED8"
    supplier_bar_outline = "#93C5FD"
    market_bar_color    = "rgba(71, 85, 105, 0.52)"
    share_line_color    = "#34D399"
    share_label_color   = "#6EE7B7"

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(
        go.Bar(
            x=period_labels,
            y=supplier_vol,
            name=supplier_legend,
            marker_color=supplier_bar_color,
            marker_line=dict(color=supplier_bar_outline, width=1.2),
            text=[f"{v:,.0f}" if v > 0 else "" for v in supplier_vol],
            textposition="inside",
            insidetextanchor="middle",
            textfont=dict(color="#FFFFFF", size=11, family="Segoe UI"),
            hovertemplate="%{x}<br>%{fullData.name}: %{y:,.1f} ton<extra></extra>",
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Bar(
            x=period_labels,
            y=other_vol,
            name=market_legend,
            marker_color=market_bar_color,
            marker_line=dict(color="rgba(148, 163, 184, 0.35)", width=0.8),
            hovertemplate="%{x}<br>%{fullData.name}: %{y:,.1f} ton<extra></extra>",
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=period_labels,
            y=[v * 1.03 for v in market_vol],
            mode="text",
            text=[f"{v:,.0f}" for v in market_vol],
            textposition="top center",
            showlegend=False,
            hoverinfo="skip",
            textfont=dict(color="#F3F4F6", size=14, family="Segoe UI"),
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=period_labels,
            y=share_vol,
            name=share_legend,
            mode="lines+markers+text",
            line=dict(color=share_line_color, width=3, shape="spline", smoothing=1.15),
            marker=dict(size=10, color=share_line_color, line=dict(width=2, color="#FFFFFF")),
            text=[f"{s:.1f}%" if s > 0 else "" for s in share_vol],
            textposition="top center",
            textfont=dict(color=share_label_color, size=11, family="Segoe UI"),
            customdata=supplier_vol,
            hovertemplate=(
                "%{x}<br>"
                f"{supplier_name} volume: %{{customdata:,.1f}} ton<br>"
                "Market share: %{y:.1f}%<extra></extra>"
            ),
        ),
        secondary_y=True,
    )

    y_max = max(market_vol) * 1.18 if market_vol else 1.0
    fig.update_layout(
        barmode="stack",
        bargap=0.28,
        height=460,
        margin=dict(l=24, r=60, t=28, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#E5E7EB", family="Segoe UI", size=12),
        template="plotly_dark",
        hovermode="closest",
        hoverlabel=dict(
            bgcolor="#1E3A5F",
            bordercolor="#2563EB",
            font_color="#FACC15",
            font_size=14,
            font=dict(color="#FACC15", size=14),
        ),
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.26,
            xanchor="center",
            x=0.5,
            bgcolor="rgba(27, 31, 35, 0.85)",
            bordercolor="#374151",
            borderwidth=1,
            font=dict(size=11, color="#E5E7EB"),
        ),
    )
    fig.update_xaxes(
        title=x_title,
        type="category",
        categoryorder="array",
        categoryarray=period_labels,
        showgrid=False,
        tickfont=dict(size=13, color="#D1D5DB"),
        linewidth=1,
        linecolor="#4B5563",
    )
    fig.update_yaxes(
        title_text="Volume (ton)",
        title_font=dict(size=12, color="#9CA3AF"),
        range=[0, y_max],
        tickformat=",",
        gridcolor="rgba(55, 65, 81, 0.45)",
        zeroline=False,
        tickfont=dict(color="#9CA3AF"),
        secondary_y=False,
    )
    fig.update_yaxes(
        title_text="Market share",
        title_font=dict(size=12, color="#9CA3AF"),
        range=[0, 65],
        ticksuffix="%",
        gridcolor="rgba(52, 211, 153, 0.12)",
        zeroline=False,
        tickfont=dict(color="#6EE7B7"),
        secondary_y=True,
    )
    st.plotly_chart(fig, use_container_width=True, key=chart_key)


def build_yearly_supplier_vs_market_data(
    df: pd.DataFrame,
    *,
    material_type: str,
    selected_supplier: str,
    type_col: str,
    supplier_col: str,
) -> pd.DataFrame:
    """
    One row per calendar year for the selected material type.

    market_ton: sum of all rows with that material in the year (all suppliers).
    supplier_ton: sum of that material sold by the selected supplier in the year.
    other_ton: market_ton - supplier_ton (remaining suppliers).
    share_pct: supplier_ton / market_ton * 100.
    """
    if df.empty or "year" not in df.columns or "volume_ton" not in df.columns:
        return pd.DataFrame()

    mt = str(material_type).strip()
    base = filter_by_material_type(df, mt, type_col=type_col)
    if base.empty:
        return pd.DataFrame()

    base["year"] = pd.to_numeric(base["year"], errors="coerce")
    base = base.dropna(subset=["year"])
    base["year"] = base["year"].astype(int)
    years = sorted(base["year"].unique().tolist())
    rows: list[dict] = []

    for year in years:
        year_df = base[base["year"] == year]
        market_ton = float(year_df["volume_ton"].sum())
        supplier_ton = _supplier_volume_in_year(year_df, supplier_col, selected_supplier)
        other_ton = max(market_ton - supplier_ton, 0.0)
        share_pct = (supplier_ton / market_ton * 100) if market_ton > 0 else 0.0
        rows.append(
            {
                "year": year,
                "supplier_ton": supplier_ton,
                "other_ton": other_ton,
                "market_ton": market_ton,
                "share_pct": round(share_pct, 1),
            }
        )

    return pd.DataFrame(rows)


def render_yearly_supplier_market_volume_chart(
    df: pd.DataFrame,
    *,
    material_type: str,
    selected_supplier: str,
    type_col: str,
    supplier_col: str,
    supplier_color_map: dict[str, str] | None = None,
    empty_message: str = "No yearly volume data for this material type.",
) -> None:
    """Stacked bars by year: selected supplier vs rest of market + market-share line."""
    year_range = format_dataset_year_range(df)
    mt_label = str(material_type).strip()
    supplier_name = format_supplier_display_name(selected_supplier)
    yearly_df = build_yearly_supplier_vs_market_data(
        df,
        material_type=material_type,
        selected_supplier=selected_supplier,
        type_col=type_col,
        supplier_col=supplier_col,
    )
    year_labels = [str(y) for y in (yearly_df["year"].astype(int).tolist() if not yearly_df.empty else [])]
    _render_supplier_market_stacked_chart(
        yearly_df.rename(columns={"year": "period"}) if not yearly_df.empty else yearly_df,
        period_labels=year_labels,
        title=f"Volume {mt_label} of {supplier_name} in {year_range}".strip(),
        supplier_name=supplier_name,
        supplier_legend=f"Volume {mt_label} of {supplier_name}" if mt_label else supplier_name,
        market_legend=f"{mt_label} market" if mt_label else OTHER_SUPPLIERS_LABEL,
        share_legend=f"{supplier_name} market share of {mt_label}" if mt_label else f"{supplier_name} market share",
        chart_key="sup_volume_by_year_chart",
        empty_message=empty_message,
    )


def render_quarterly_supplier_market_volume_chart(
    df: pd.DataFrame,
    *,
    material_type: str,
    selected_supplier: str,
    type_col: str,
    supplier_col: str,
    year: int,
    empty_message: str = "No quarterly volume data for this material type.",
) -> None:
    """Stacked bars by quarter for the selected year."""
    mt_label = str(material_type).strip()
    supplier_name = format_supplier_display_name(selected_supplier)
    year_df = df[df["year"] == year].copy() if "year" in df.columns else df.copy()
    period_df = _build_period_supplier_vs_market_data(
        year_df,
        material_type=material_type,
        selected_supplier=selected_supplier,
        type_col=type_col,
        supplier_col=supplier_col,
        period_col="quarter",
        period_order=QUARTER_ORDER,
    )
    quarter_order_keys = [q for q, _ in sorted(QUARTER_ORDER.items(), key=lambda x: x[1])]
    period_labels = []
    if not period_df.empty:
        period_df["period"] = period_df["period"].astype(str).str.lower()
        period_df = period_df.sort_values("period", key=lambda s: s.map(lambda q: QUARTER_ORDER.get(q, 99)))
        period_labels = [p.upper() for p in period_df["period"].tolist()]
    _render_supplier_market_stacked_chart(
        period_df,
        period_labels=period_labels,
        title=f"Volume {mt_label} of {supplier_name} by Quarter ({year})",
        supplier_name=supplier_name,
        supplier_legend=f"Volume {mt_label} of {supplier_name}" if mt_label else supplier_name,
        market_legend=f"{mt_label} market" if mt_label else OTHER_SUPPLIERS_LABEL,
        share_legend=f"{supplier_name} market share of {mt_label}" if mt_label else f"{supplier_name} market share",
        chart_key="sup_volume_by_quarter_chart",
        x_title="Quarter",
        empty_message=empty_message,
    )


def render_monthly_supplier_market_volume_chart(
    df: pd.DataFrame,
    *,
    material_type: str,
    selected_supplier: str,
    type_col: str,
    supplier_col: str,
    year: int,
    empty_message: str = "No monthly volume data for this material type.",
) -> None:
    """Stacked bars by month for the selected year."""
    mt_label = str(material_type).strip()
    supplier_name = format_supplier_display_name(selected_supplier)
    year_df = df[df["year"] == year].copy() if "year" in df.columns else df.copy()
    period_df = _build_period_supplier_vs_market_data(
        year_df,
        material_type=material_type,
        selected_supplier=selected_supplier,
        type_col=type_col,
        supplier_col=supplier_col,
        period_col="month",
        period_order=MONTH_ORDER,
    )
    period_labels = []
    if not period_df.empty:
        period_df["period"] = period_df["period"].astype(str).str.lower()
        period_df = period_df.sort_values("period", key=lambda s: s.map(lambda m: MONTH_ORDER.get(m, 99)))
        period_labels = [p.upper() for p in period_df["period"].tolist()]
    _render_supplier_market_stacked_chart(
        period_df,
        period_labels=period_labels,
        title=f"Volume {mt_label} of {supplier_name} by Month ({year})",
        supplier_name=supplier_name,
        supplier_legend=f"Volume {mt_label} of {supplier_name}" if mt_label else supplier_name,
        market_legend=f"{mt_label} market" if mt_label else OTHER_SUPPLIERS_LABEL,
        share_legend=f"{supplier_name} market share of {mt_label}" if mt_label else f"{supplier_name} market share",
        chart_key="sup_volume_by_month_chart",
        x_title="Month",
        empty_message=empty_message,
    )


def _format_compare_period_label(period: str, period_col: str) -> str:
    if period_col == "year":
        return str(period)
    if period_col == "quarter":
        return str(period).upper()
    month_key = str(period).lower()
    month_num = MONTH_ORDER.get(month_key)
    if month_num and 1 <= month_num <= 12:
        return MONTH_DISPLAY[month_num - 1]
    return str(period).upper()


def build_multi_supplier_period_metrics(
    df: pd.DataFrame,
    *,
    material_type: str,
    suppliers: list[str],
    type_col: str,
    supplier_col: str,
    period_col: str,
    period_order: dict[str, int] | None = None,
    year_filter: int | None = None,
) -> tuple[pd.DataFrame, list[str], list[str]]:
    """
    Long-format metrics for supplier comparison.
    Returns (metrics_df, period_keys, period_labels).
    """
    empty = pd.DataFrame(columns=["period", "supplier", "volume_ton", "market_ton", "share_pct"])
    if df.empty or not suppliers or period_col not in df.columns:
        return empty, [], []

    base = filter_by_material_type(df, material_type, type_col=type_col)
    if year_filter is not None and "year" in base.columns:
        base = base[base["year"] == year_filter].copy()
    if base.empty:
        return empty, [], []

    work = base.copy()
    if period_col == "year":
        work[period_col] = pd.to_numeric(work[period_col], errors="coerce")
        work = work.dropna(subset=[period_col])
        work[period_col] = work[period_col].astype(int).astype(str)
    else:
        work[period_col] = work[period_col].astype(str).str.strip().str.lower()

    if period_col == "year":
        period_keys = sorted(work[period_col].unique().tolist(), key=lambda p: int(p))
    elif period_order:
        period_keys = sorted(
            work[period_col].dropna().unique().tolist(),
            key=lambda p: period_order.get(str(p).lower(), 99),
        )
    else:
        period_keys = sorted(work[period_col].dropna().unique().tolist())

    rows: list[dict] = []
    for period in period_keys:
        period_df = work[work[period_col].astype(str) == str(period)]
        market_ton = float(period_df["volume_ton"].sum())
        for sup in suppliers:
            sel = str(sup).strip().casefold()
            mask = period_df[supplier_col].astype(str).str.strip().str.casefold() == sel
            vol = float(period_df.loc[mask, "volume_ton"].sum())
            share_pct = (vol / market_ton * 100) if market_ton > 0 else 0.0
            rows.append(
                {
                    "period": str(period),
                    "supplier": sup,
                    "volume_ton": vol,
                    "market_ton": market_ton,
                    "share_pct": round(share_pct, 1),
                }
            )

    metrics_df = pd.DataFrame(rows)
    period_labels = [_format_compare_period_label(p, period_col) for p in period_keys]
    return metrics_df, period_keys, period_labels


def _supplier_series_by_period(
    metrics_df: pd.DataFrame,
    *,
    supplier: str,
    period_keys: list[str],
    value_col: str,
) -> list[float]:
    sub = metrics_df[metrics_df["supplier"] == supplier].set_index("period")
    values: list[float] = []
    for period in period_keys:
        key = str(period)
        if key in sub.index:
            values.append(float(sub.loc[key, value_col]))
        else:
            values.append(0.0)
    return values


def _format_compare_volume_chart_title(
    *,
    material_type: str,
    sale_channel: str,
    period_mode: str,
    year_int: int,
    period_caption: str,
) -> str:
    mt_label = str(material_type).strip()
    channel = str(sale_channel).strip()
    if period_mode == "Yearly":
        return f"Compare supplier volume · {mt_label} · {period_caption}"
    if period_mode == "Quarterly":
        return f"Supplier Volume Comparison: {mt_label} vs. {channel} (Quarterly {year_int})"
    if period_mode == "Monthly":
        return f"Supplier Volume Comparison: {mt_label} vs. {channel} (Monthly {year_int})"
    return f"Compare supplier volume · {mt_label} · {period_caption}"


def _format_compare_share_chart_title(
    *,
    material_type: str,
    sale_channel: str,
    period_mode: str,
    year_int: int,
    period_caption: str,
) -> str:
    mt_label = str(material_type).strip()
    channel = str(sale_channel).strip()
    if period_mode == "Yearly":
        return f"Compare market share · {mt_label} · {period_caption}"
    if period_mode == "Quarterly":
        return f"Supplier Market Share Comparison: {mt_label} vs. {channel} (Quarterly {year_int})"
    if period_mode == "Monthly":
        return f"Supplier Market Share Comparison: {mt_label} vs. {channel} (Monthly {year_int})"
    return f"Compare market share · {mt_label} · {period_caption}"


def render_supplier_compare_volume_chart(
    metrics_df: pd.DataFrame,
    *,
    suppliers: list[str],
    period_labels: list[str],
    period_keys: list[str],
    material_type: str,
    color_map: dict[str, str],
    period_mode: str,
    year_int: int,
    sale_channel: str,
    period_caption: str,
    empty_message: str = "No volume data for the selected suppliers.",
) -> None:
    """Grouped bars: volume (ton) per supplier across periods."""
    import plotly.graph_objects as go

    title = _format_compare_volume_chart_title(
        material_type=material_type,
        sale_channel=sale_channel,
        period_mode=period_mode,
        year_int=year_int,
        period_caption=period_caption,
    )
    chart_card_title(title, large=True)
    if metrics_df.empty or not period_labels:
        st.info(empty_message)
        return

    fig = go.Figure()
    compare_bar_colors = build_supplier_compare_color_map(suppliers)
    for i, sup in enumerate(suppliers):
        display_name = format_supplier_display_name(sup)
        vols = _supplier_series_by_period(
            metrics_df, supplier=sup, period_keys=period_keys, value_col="volume_ton"
        )
        fig.add_trace(
            go.Bar(
                x=period_labels,
                y=vols,
                name=display_name,
                marker_color=_supplier_color(compare_bar_colors, sup),
                hovertemplate="%{x}<br>%{fullData.name}: %{y:,.1f} ton<extra></extra>",
            )
        )

    fig.update_layout(
        barmode="group",
        bargap=0.18,
        bargroupgap=0.08,
        height=420,
        margin=dict(l=20, r=20, t=12, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#E5E7EB"),
        template="plotly_dark",
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.18,
            xanchor="center",
            x=0.5,
            font=dict(size=11, color="#E5E7EB"),
        ),
        xaxis=dict(title="", showgrid=False),
        yaxis=dict(title="Volume (ton)", gridcolor="#374151", tickformat=","),
    )
    st.plotly_chart(fig, use_container_width=True, key="sup_compare_volume_chart")


def render_supplier_compare_share_chart(
    metrics_df: pd.DataFrame,
    *,
    suppliers: list[str],
    period_labels: list[str],
    period_keys: list[str],
    material_type: str,
    color_map: dict[str, str],
    period_mode: str,
    year_int: int,
    sale_channel: str,
    period_caption: str,
    empty_message: str = "No market share data for the selected suppliers.",
) -> None:
    """Multi-line chart: market share % per supplier across periods."""
    import plotly.graph_objects as go

    title = _format_compare_share_chart_title(
        material_type=material_type,
        sale_channel=sale_channel,
        period_mode=period_mode,
        year_int=year_int,
        period_caption=period_caption,
    )
    chart_card_title(title, large=True)
    if metrics_df.empty or not period_labels:
        st.info(empty_message)
        return

    fig = go.Figure()
    compare_colors = build_supplier_compare_color_map(suppliers)
    for sup in suppliers:
        display_name = format_supplier_display_name(sup)
        shares = _supplier_series_by_period(
            metrics_df, supplier=sup, period_keys=period_keys, value_col="share_pct"
        )
        line_color = _supplier_color(compare_colors, sup)
        fig.add_trace(
            go.Scatter(
                x=period_labels,
                y=shares,
                name=display_name,
                mode="lines+markers",
                line=dict(color=line_color, width=2.5),
                marker=dict(size=8, color=line_color),
                hovertemplate="%{x}<br>%{fullData.name}: %{y:.1f}%<extra></extra>",
            )
        )

    y_max = max(
        [v for sup in suppliers for v in _supplier_series_by_period(
            metrics_df, supplier=sup, period_keys=period_keys, value_col="share_pct"
        )],
        default=0.0,
    )
    fig.update_layout(
        height=380,
        margin=dict(l=20, r=20, t=12, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#E5E7EB"),
        template="plotly_dark",
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.2,
            xanchor="center",
            x=0.5,
            font=dict(size=11, color="#E5E7EB"),
        ),
        xaxis=dict(title="", showgrid=False),
        yaxis=dict(
            title="Market share (%)",
            gridcolor="#374151",
            ticksuffix="%",
            range=[0, max(y_max * 1.2, 10.0)],
        ),
    )
    st.plotly_chart(fig, use_container_width=True, key="sup_compare_share_chart")


def render_supplier_compare_dashboard(
    df: pd.DataFrame,
    *,
    material_type: str,
    suppliers: list[str],
    type_col: str,
    supplier_col: str,
    period_mode: str,
    year_int: int,
    sale_channel: str,
    supplier_color_map: dict[str, str],
) -> None:
    """Compare mode: grouped volume bars + share lines."""
    if period_mode == "Yearly":
        period_col = "year"
        period_order = None
        year_filter = None
        period_caption = f"{sale_channel} · all years"
    elif period_mode == "Quarterly":
        period_col = "quarter"
        period_order = QUARTER_ORDER
        year_filter = year_int
        period_caption = f"{sale_channel} · {year_int}"
    else:
        period_col = "month"
        period_order = MONTH_ORDER
        year_filter = year_int
        period_caption = f"{sale_channel} · {year_int}"

    metrics_df, period_keys, period_labels = build_multi_supplier_period_metrics(
        df,
        material_type=material_type,
        suppliers=suppliers,
        type_col=type_col,
        supplier_col=supplier_col,
        period_col=period_col,
        period_order=period_order,
        year_filter=year_filter,
    )
    if metrics_df.empty:
        st.warning("No comparison data for the selected filters and suppliers.")
        return

    render_supplier_compare_volume_chart(
        metrics_df,
        suppliers=suppliers,
        period_labels=period_labels,
        period_keys=period_keys,
        material_type=material_type,
        color_map=supplier_color_map,
        period_mode=period_mode,
        year_int=year_int,
        sale_channel=sale_channel,
        period_caption=period_caption,
    )
    render_supplier_compare_share_chart(
        metrics_df,
        suppliers=suppliers,
        period_labels=period_labels,
        period_keys=period_keys,
        material_type=material_type,
        color_map=supplier_color_map,
        period_mode=period_mode,
        year_int=year_int,
        sale_channel=sale_channel,
        period_caption=period_caption,
    )


def render_yearly_volume_market_share_chart(
    df: pd.DataFrame,
    *,
    material_type: str,
    selected_supplier: str,
    type_col: str,
    supplier_col: str,
    supplier_color_map: dict[str, str] | None = None,
    empty_message: str = "No yearly volume data for this material type.",
) -> None:
    """Stacked bars: top 5 supplier volume per year; line: selected supplier market share %."""
    year_range = format_dataset_year_range(df)
    mt_label = str(material_type).strip()
    title = f"Volume by year {year_range} · {mt_label}".strip() if mt_label else f"Volume by year {year_range}".strip()
    chart_card_title(title, large=True)
    stack_df, share_df = build_yearly_top5_share_data(
        df,
        material_type=material_type,
        selected_supplier=selected_supplier,
        type_col=type_col,
        supplier_col=supplier_col,
    )
    if stack_df.empty or share_df.empty:
        st.info(empty_message)
        return

    import plotly.graph_objects as go

    years = sorted(stack_df["year"].unique().astype(int).tolist())
    year_labels = [str(y) for y in years]
    if supplier_color_map is None:
        supplier_color_map = supplier_color_map_for_material(
            df, material_type=material_type, type_col=type_col, supplier_col=supplier_col
        )
    named_suppliers = (
        stack_df[stack_df["supplier"] != TOP5_OTHERS_LABEL]
        .groupby("supplier")["volume_ton"]
        .sum()
        .sort_values(ascending=False)
        .index.tolist()
    )
    supplier_name = format_supplier_display_name(selected_supplier)
    sel_ton_by_year = (
        share_df.set_index("year")["supplier_ton"].reindex(years, fill_value=0).astype(float).tolist()
    )
    market_ton_by_year = (
        share_df.set_index("year")["market_ton"].reindex(years, fill_value=0).astype(float).tolist()
    )

    fig = go.Figure()
    for supplier in named_suppliers:
        sub = stack_df[stack_df["supplier"] == supplier]
        vol_by_year = sub.set_index("year")["volume_ton"].reindex(years, fill_value=0)
        fig.add_trace(
            go.Bar(
                x=year_labels,
                y=vol_by_year.values,
                name=format_supplier_display_name(supplier),
                marker_color=_supplier_color(supplier_color_map, supplier),
                yaxis="y",
                legendgroup=supplier,
                hovertemplate="%{x}<br>%{fullData.name}: %{y:,.1f} ton<extra></extra>",
                hoverlabel=YEARLY_STACK_BAR_HOVERLABEL,
            )
        )
    if (stack_df["supplier"] == TOP5_OTHERS_LABEL).any():
        others_sub = stack_df[stack_df["supplier"] == TOP5_OTHERS_LABEL]
        others_by_year = others_sub.set_index("year")["volume_ton"].reindex(years, fill_value=0)
        fig.add_trace(
            go.Bar(
                x=year_labels,
                y=others_by_year.values,
                name=TOP5_OTHERS_LABEL,
                marker_color="#6B7280",
                yaxis="y",
                legendgroup=TOP5_OTHERS_LABEL,
                hovertemplate="%{x}<br>%{fullData.name}: %{y:,.1f} ton<extra></extra>",
                hoverlabel=YEARLY_STACK_BAR_HOVERLABEL,
            )
        )

    total_volume_by_year = market_ton_by_year
    fig.add_trace(
        go.Scatter(
            x=year_labels,
            y=[v * 1.01 for v in total_volume_by_year],
            mode="text",
            text=[f"{v:,.0f}" for v in total_volume_by_year],
            textposition="top center",
            showlegend=False,
            hoverinfo="skip",
            textfont=dict(color="#E5E7EB", size=14, family="Arial Black"),
        )
    )

    share_by_year = share_df.set_index("year")["share_pct"].reindex(years, fill_value=0)
    fig.add_trace(
        go.Scatter(
            x=year_labels,
            y=share_by_year.values,
            name=f"{supplier_name} market share",
            mode="lines+markers",
            line=dict(color=CHART["red"], width=2.5),
            marker=dict(size=8, color=CHART["red"]),
            yaxis="y2",
            customdata=sel_ton_by_year,
            hovertemplate=(
                "%{x}<br>"
                f"{supplier_name} volume: %{{customdata:,.1f}} ton<br>"
                "Market share: %{y:.1f}%<extra></extra>"
            ),
            hoverlabel=YEARLY_SHARE_LINE_HOVERLABEL,
        )
    )

    fig.update_layout(
        barmode="stack",
        height=420,
        margin=dict(l=20, r=48, t=12, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#E5E7EB"),
        template="plotly_dark",
        hovermode="closest",
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.22,
            xanchor="center",
            x=0.5,
            font=dict(size=11, color="#E5E7EB"),
        ),
        xaxis=dict(title="", showgrid=False),
        yaxis=dict(
            title="Volume",
            gridcolor="#374151",
            tickformat=",",
        ),
        yaxis2=dict(
            title="Market share",
            overlaying="y",
            side="right",
            range=[0, 65],
            ticksuffix="%",
            gridcolor="rgba(55,65,81,0.35)",
        ),
    )
    st.plotly_chart(fig, use_container_width=True)


MONTH_KEYS = [m for m, _ in sorted(MONTH_ORDER.items(), key=lambda x: x[1])]
MONTH_DISPLAY = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
DEEP_DIVE_YEAR_LINE_COLORS = ["#3B82F6", "#F59E0B", "#10B981", "#A78BFA", "#22D3EE", "#EF4444"]

MONTHLY_DEEP_DIVE_HOVERLABEL = dict(
    bgcolor="#0A0A0A",
    bordercolor="#404040",
    font=dict(color="#FFFFFF", size=12),
)


def _rgba_hex(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def _monthly_series_by_year(base: pd.DataFrame) -> tuple[list[int], dict[int, list[float]]]:
    """Jan–Dec volume (ton) per year from a pre-filtered dataframe."""
    if base.empty or "month" not in base.columns:
        return [], {}
    work = base.copy()
    work["month"] = work["month"].astype(str).str.strip().str.lower()
    years = sorted(pd.to_numeric(work["year"], errors="coerce").dropna().astype(int).unique().tolist())
    series: dict[int, list[float]] = {}
    for year in years:
        year_df = work[work["year"] == year]
        monthly = monthly_volume_ton(year_df)
        monthly["month"] = monthly["month"].astype(str).str.lower()
        vols: list[float] = []
        for mk in MONTH_KEYS:
            row = monthly[monthly["month"] == mk]
            vols.append(float(row["volume_ton"].sum()) if not row.empty else 0.0)
        series[year] = vols
    return years, series


def _market_monthly_series_by_year(
    df: pd.DataFrame,
    *,
    material_type: str,
    type_col: str,
) -> tuple[list[int], dict[int, list[float]]]:
    """Per calendar year: Jan–Dec total volume (ton) — all suppliers combined."""
    if df.empty or "month" not in df.columns:
        return [], {}
    base = filter_by_material_type(df, material_type, type_col=type_col)
    return _monthly_series_by_year(base)


def _supplier_monthly_series_by_year(
    df: pd.DataFrame,
    *,
    material_type: str,
    selected_supplier: str,
    type_col: str,
    supplier_col: str,
) -> tuple[list[int], dict[int, list[float]]]:
    """Per calendar year: Jan–Dec volume (ton) for one supplier."""
    if df.empty or "month" not in df.columns:
        return [], {}
    base = filter_by_material_type(df, material_type, type_col=type_col)
    base = base[base[supplier_col] == selected_supplier].copy()
    return _monthly_series_by_year(base)


def render_monthly_deep_dive_chart(
    df: pd.DataFrame,
    *,
    material_type: str,
    type_col: str,
    empty_message: str = "No monthly volume for this material type.",
) -> None:
    """Area line chart: total market volume by month (Jan–Dec), all suppliers, one line per year."""
    chart_card_title("Monthly deep dive", large=True)
    mt = str(material_type).strip()
    st.markdown(
        f'<div class="chart-subtitle-lg">Monthly volumes {mt} (all suppliers)</div>',
        unsafe_allow_html=True,
    )

    years, series = _market_monthly_series_by_year(
        df,
        material_type=material_type,
        type_col=type_col,
    )
    if not years:
        st.info(empty_message)
        return

    _plot_monthly_deep_dive(years, series, hover_volume_label="Total volume")


def _plot_monthly_deep_dive(
    years: list[int],
    series: dict[int, list[float]],
    *,
    hover_volume_label: str = "Volume",
    chart_height: int = 400,
) -> None:
    import plotly.graph_objects as go

    fig = go.Figure()
    max_vol = 0.0
    for i, year in enumerate(years):
        vols = series[year]
        max_vol = max(max_vol, max(vols) if vols else 0.0)
        color = DEEP_DIVE_YEAR_LINE_COLORS[i % len(DEEP_DIVE_YEAR_LINE_COLORS)]
        fig.add_trace(
            go.Scatter(
                x=MONTH_DISPLAY,
                y=vols,
                name=str(year),
                mode="lines",
                line=dict(color=color, width=2.5, shape="spline", smoothing=1.1),
                fill="tozeroy",
                fillcolor=_rgba_hex(color, 0.22),
                hovertemplate=(
                    "<b>%{x} %{fullData.name}</b><br>"
                    f"<b>{hover_volume_label}: %{{y:,.1f}} ton</b>"
                    "<extra></extra>"
                ),
            )
        )

    y_max = max(max_vol * 1.15, 1.0)
    fig.update_layout(
        height=chart_height,
        margin=dict(l=12, r=12, t=32, b=52),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#E5E7EB", size=11),
        template="plotly_dark",
        hovermode="x unified",
        hoverlabel=MONTHLY_DEEP_DIVE_HOVERLABEL,
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.28,
            xanchor="center",
            x=0.5,
            font=dict(size=13, color="#E5E7EB"),
        ),
        xaxis=dict(
            title="",
            showgrid=False,
            categoryorder="array",
            categoryarray=MONTH_DISPLAY,
        ),
        yaxis=dict(
            title="",
            range=[0, y_max],
            gridcolor="#374151",
            tickformat=".2~s",
        ),
    )
    st.plotly_chart(fig, use_container_width=True)


def render_monthly_deep_dive_supplier_chart(
    df: pd.DataFrame,
    *,
    material_type: str,
    selected_supplier: str,
    type_col: str,
    supplier_col: str,
    empty_message: str = "No monthly volume for this supplier.",
) -> None:
    """Area line chart: selected supplier volume by month (Jan–Dec), one line per year."""
    chart_card_title("Monthly deep dive for supplier selected", large=True)
    mt = str(material_type).strip()
    st.markdown(
        f'<div class="chart-subtitle-lg">Monthly volumes {mt} · <strong>{selected_supplier}</strong></div>',
        unsafe_allow_html=True,
    )

    years, series = _supplier_monthly_series_by_year(
        df,
        material_type=material_type,
        selected_supplier=selected_supplier,
        type_col=type_col,
        supplier_col=supplier_col,
    )
    if not years:
        st.info(empty_message)
        return

    _plot_monthly_deep_dive(years, series, hover_volume_label="Volume")


# ── Tab 3: Customer deep dive ───────────────────────────────────────────────

OTHER_CUSTOMERS_LABEL = "Other customers"


def _customer_volume_in_df(
    frame: pd.DataFrame,
    customer_col: str,
    customer_id: str,
) -> float:
    if frame.empty or customer_col not in frame.columns:
        return 0.0
    sel = str(customer_id).strip()
    mask = frame[customer_col].astype(str).str.strip() == sel
    return float(frame.loc[mask, "volume_ton"].sum())


def build_yearly_customer_vs_market_data(
    df: pd.DataFrame,
    *,
    material_type: str,
    customer_id: str,
    type_col: str,
    customer_col: str,
) -> pd.DataFrame:
    if df.empty or "year" not in df.columns or "volume_ton" not in df.columns:
        return pd.DataFrame()

    base = filter_by_material_type(df, str(material_type).strip(), type_col=type_col)
    if base.empty:
        return pd.DataFrame()

    base["year"] = pd.to_numeric(base["year"], errors="coerce")
    base = base.dropna(subset=["year"])
    base["year"] = base["year"].astype(int)
    rows: list[dict] = []
    for year in sorted(base["year"].unique().tolist()):
        year_df = base[base["year"] == year]
        market_ton = float(year_df["volume_ton"].sum())
        customer_ton = _customer_volume_in_df(year_df, customer_col, customer_id)
        other_ton = max(market_ton - customer_ton, 0.0)
        share_pct = (customer_ton / market_ton * 100) if market_ton > 0 else 0.0
        rows.append(
            {
                "year": year,
                "supplier_ton": customer_ton,
                "other_ton": other_ton,
                "market_ton": market_ton,
                "share_pct": round(share_pct, 1),
            }
        )
    return pd.DataFrame(rows)


def _build_period_customer_vs_market_data(
    df: pd.DataFrame,
    *,
    material_type: str,
    customer_id: str,
    type_col: str,
    customer_col: str,
    period_col: str,
    period_order: dict[str, int],
) -> pd.DataFrame:
    if df.empty or period_col not in df.columns or "volume_ton" not in df.columns:
        return pd.DataFrame()
    base = filter_by_material_type(df, str(material_type).strip(), type_col=type_col)
    if base.empty:
        return pd.DataFrame()
    base[period_col] = base[period_col].astype(str).str.strip().str.lower()
    periods = sorted(
        base[period_col].dropna().unique().tolist(),
        key=lambda p: period_order.get(p, 99),
    )
    rows: list[dict] = []
    for period in periods:
        period_df = base[base[period_col] == period]
        market_ton = float(period_df["volume_ton"].sum())
        customer_ton = _customer_volume_in_df(period_df, customer_col, customer_id)
        other_ton = max(market_ton - customer_ton, 0.0)
        share_pct = (customer_ton / market_ton * 100) if market_ton > 0 else 0.0
        rows.append(
            {
                "period": period,
                "supplier_ton": customer_ton,
                "other_ton": other_ton,
                "market_ton": market_ton,
                "share_pct": round(share_pct, 1),
            }
        )
    return pd.DataFrame(rows)


def render_yearly_customer_market_volume_chart(
    df: pd.DataFrame,
    *,
    material_type: str,
    customer_id: str,
    customer_name: str,
    type_col: str,
    customer_col: str,
    empty_message: str = "No yearly volume data for this customer.",
) -> None:
    year_range = format_dataset_year_range(df)
    mt_label = str(material_type).strip()
    display_name = format_customer_display_name(customer_name)
    yearly_df = build_yearly_customer_vs_market_data(
        df,
        material_type=material_type,
        customer_id=customer_id,
        type_col=type_col,
        customer_col=customer_col,
    )
    year_labels = [
        str(y) for y in (yearly_df["year"].astype(int).tolist() if not yearly_df.empty else [])
    ]
    _render_supplier_market_stacked_chart(
        yearly_df.rename(columns={"year": "period"}) if not yearly_df.empty else yearly_df,
        period_labels=year_labels,
        title=f"Import volume {mt_label} · {display_name} · {year_range}".strip(),
        supplier_name=display_name,
        supplier_legend=f"{display_name} import volume" if mt_label else display_name,
        market_legend=f"{mt_label} market" if mt_label else OTHER_CUSTOMERS_LABEL,
        share_legend=f"{display_name} market share of {mt_label}" if mt_label else f"{display_name} market share",
        chart_key="cust_volume_by_year_chart",
        empty_message=empty_message,
    )


def render_quarterly_customer_market_volume_chart(
    df: pd.DataFrame,
    *,
    material_type: str,
    customer_id: str,
    customer_name: str,
    type_col: str,
    customer_col: str,
    year: int,
    empty_message: str = "No quarterly volume data for this customer.",
) -> None:
    mt_label = str(material_type).strip()
    display_name = format_customer_display_name(customer_name)
    year_df = df[df["year"] == year].copy() if "year" in df.columns else df.copy()
    period_df = _build_period_customer_vs_market_data(
        year_df,
        material_type=material_type,
        customer_id=customer_id,
        type_col=type_col,
        customer_col=customer_col,
        period_col="quarter",
        period_order=QUARTER_ORDER,
    )
    period_labels = []
    if not period_df.empty:
        period_df["period"] = period_df["period"].astype(str).str.lower()
        period_df = period_df.sort_values(
            "period", key=lambda s: s.map(lambda q: QUARTER_ORDER.get(q, 99))
        )
        period_labels = [p.upper() for p in period_df["period"].tolist()]
    _render_supplier_market_stacked_chart(
        period_df,
        period_labels=period_labels,
        title=f"Import volume {mt_label} · {display_name} by Quarter ({year})",
        supplier_name=display_name,
        supplier_legend=f"{display_name} import volume" if mt_label else display_name,
        market_legend=f"{mt_label} market" if mt_label else OTHER_CUSTOMERS_LABEL,
        share_legend=f"{display_name} market share of {mt_label}" if mt_label else f"{display_name} market share",
        chart_key="cust_volume_by_quarter_chart",
        x_title="Quarter",
        empty_message=empty_message,
    )


def render_monthly_customer_market_volume_chart(
    df: pd.DataFrame,
    *,
    material_type: str,
    customer_id: str,
    customer_name: str,
    type_col: str,
    customer_col: str,
    year: int,
    empty_message: str = "No monthly volume data for this customer.",
) -> None:
    mt_label = str(material_type).strip()
    display_name = format_customer_display_name(customer_name)
    year_df = df[df["year"] == year].copy() if "year" in df.columns else df.copy()
    period_df = _build_period_customer_vs_market_data(
        year_df,
        material_type=material_type,
        customer_id=customer_id,
        type_col=type_col,
        customer_col=customer_col,
        period_col="month",
        period_order=MONTH_ORDER,
    )
    period_labels = []
    if not period_df.empty:
        period_df["period"] = period_df["period"].astype(str).str.lower()
        period_df = period_df.sort_values(
            "period", key=lambda s: s.map(lambda m: MONTH_ORDER.get(m, 99))
        )
        period_labels = [p.upper() for p in period_df["period"].tolist()]
    _render_supplier_market_stacked_chart(
        period_df,
        period_labels=period_labels,
        title=f"Import volume {mt_label} · {display_name} by Month ({year})",
        supplier_name=display_name,
        supplier_legend=f"{display_name} import volume" if mt_label else display_name,
        market_legend=f"{mt_label} market" if mt_label else OTHER_CUSTOMERS_LABEL,
        share_legend=f"{display_name} market share of {mt_label}" if mt_label else f"{display_name} market share",
        chart_key="cust_volume_by_month_chart",
        x_title="Month",
        empty_message=empty_message,
    )


def build_customer_supplier_mix_data(
    df: pd.DataFrame,
    *,
    material_type: str,
    customer_id: str,
    type_col: str,
    customer_col: str,
    supplier_col: str,
) -> pd.DataFrame:
    if df.empty or supplier_col not in df.columns:
        return pd.DataFrame(columns=["supplier", "volume_ton", "share_pct"])

    base = filter_by_material_type(df, str(material_type).strip(), type_col=type_col)
    base = base[base[customer_col].astype(str).str.strip() == str(customer_id).strip()]
    if base.empty:
        return pd.DataFrame(columns=["supplier", "volume_ton", "share_pct"])

    grouped = (
        base.groupby(supplier_col, dropna=False)["volume_ton"]
        .sum()
        .reset_index()
        .sort_values("volume_ton", ascending=False)
    )
    total = float(grouped["volume_ton"].sum())
    grouped = grouped.rename(columns={supplier_col: "supplier"})
    grouped["share_pct"] = (
        (grouped["volume_ton"] / total * 100).round(1) if total > 0 else 0.0
    )
    return grouped


def render_customer_supplier_mix_chart(
    df: pd.DataFrame,
    *,
    material_type: str,
    customer_id: str,
    customer_name: str,
    type_col: str,
    customer_col: str,
    supplier_col: str,
    year: int,
    sale_channel: str,
    side_panel: bool = False,
    empty_message: str = "No supplier mix data for this customer.",
) -> None:
    import plotly.graph_objects as go

    display_name = format_customer_display_name(customer_name)
    mt_label = str(material_type).strip()

    if side_panel:
        chart_df, n_suppliers = build_customer_suppliers_ranked_data(
            df,
            supplier_col=supplier_col,
        )
        chart_card_title(f"Supplier mix · Year {year}", large=True)
        chart_footnote(
            f"{display_name} · {mt_label} · {sale_channel} · "
            f"{n_suppliers:,} suppliers"
        )
        if chart_df.empty:
            st.info(empty_message)
            return

        raw_suppliers = chart_df["supplier_label"].astype(str).tolist()
        compare_colors = build_supplier_compare_color_map(raw_suppliers)
        colors = [_supplier_color(compare_colors, s) for s in raw_suppliers]
        labels = raw_suppliers
        volumes = chart_df["volume_ton"].astype(float).tolist()
        shares = chart_df["share_pct"].astype(float).tolist()
        max_vol = float(max(volumes)) if volumes else 0.0
        inside_text = [
            f"{v:,.0f}" if max_vol > 0 and v >= max_vol * 0.07 else ""
            for v in volumes
        ]
        fig = go.Figure(
            go.Bar(
                x=volumes,
                y=labels,
                orientation="h",
                marker_color=colors,
                text=inside_text,
                textposition="inside",
                insidetextanchor="middle",
                textfont=dict(color="#FFFFFF", size=10),
                customdata=shares,
                hovertemplate=(
                    "%{y}<br>Volume: %{x:,.1f} ton<br>Share: %{customdata:.1f}%<extra></extra>"
                ),
                hoverlabel=PERIOD_CUSTOMER_VOLUME_HOVERLABEL,
            )
        )
        x_max = max_vol * 1.15 if max_vol > 0 else 1.0
        fig.update_layout(
            height=_ranked_bar_chart_height(len(labels), cap=None),
            margin=dict(l=12, r=12, t=12, b=20),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#E5E7EB", family="Segoe UI", size=12),
            template="plotly_dark",
            showlegend=False,
            hoverlabel=PERIOD_CUSTOMER_VOLUME_HOVERLABEL,
            xaxis=dict(title="Volume (ton)", range=[0, x_max], tickformat=","),
            yaxis=dict(title="", autorange="reversed"),
        )
        st.plotly_chart(fig, use_container_width=True, key="cust_supplier_mix_chart")
        return

    chart_card_title(
        f"Supplier mix · {display_name} · {mt_label} · {sale_channel} · {year}",
        large=True,
    )
    mix_df = build_customer_supplier_mix_data(
        df,
        material_type=material_type,
        customer_id=customer_id,
        type_col=type_col,
        customer_col=customer_col,
        supplier_col=supplier_col,
    )
    if mix_df.empty:
        st.info(empty_message)
        return

    suppliers = mix_df["supplier"].astype(str).tolist()
    compare_colors = build_supplier_compare_color_map(suppliers)
    colors = [_supplier_color(compare_colors, s) for s in suppliers]
    labels = [format_supplier_display_name(s) for s in suppliers]

    fig = go.Figure(
        go.Bar(
            x=mix_df["volume_ton"].astype(float).tolist(),
            y=labels,
            orientation="h",
            marker_color=colors,
            text=[f"{v:,.1f} ton · {p:.1f}%" for v, p in zip(mix_df["volume_ton"], mix_df["share_pct"])],
            textposition="outside",
            textfont=dict(color="#E5E7EB", size=11),
            hovertemplate="%{y}<br>Volume: %{x:,.1f} ton<extra></extra>",
        )
    )
    x_max = float(mix_df["volume_ton"].max()) * 1.25 if not mix_df.empty else 1.0
    fig.update_layout(
        height=max(280, 48 * len(labels) + 80),
        margin=dict(l=20, r=40, t=12, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#E5E7EB"),
        template="plotly_dark",
        showlegend=False,
        xaxis=dict(title="Volume (ton)", range=[0, x_max], tickformat=","),
        yaxis=dict(title="", autorange="reversed"),
    )
    st.plotly_chart(fig, use_container_width=True, key="cust_supplier_mix_chart")


def build_multi_customer_period_metrics(
    df: pd.DataFrame,
    *,
    material_type: str,
    customer_ids: list[str],
    type_col: str,
    customer_col: str,
    period_col: str,
    period_order: dict[str, int] | None = None,
    year_filter: int | None = None,
) -> tuple[pd.DataFrame, list[str], list[str]]:
    empty = pd.DataFrame(columns=["period", "customer_id", "volume_ton", "market_ton", "share_pct"])
    if df.empty or not customer_ids or period_col not in df.columns:
        return empty, [], []

    base = filter_by_material_type(df, material_type, type_col=type_col)
    if year_filter is not None and "year" in base.columns:
        base = base[base["year"] == year_filter].copy()
    if base.empty:
        return empty, [], []

    work = base.copy()
    if period_col == "year":
        work[period_col] = pd.to_numeric(work[period_col], errors="coerce")
        work = work.dropna(subset=[period_col])
        work[period_col] = work[period_col].astype(int).astype(str)
    else:
        work[period_col] = work[period_col].astype(str).str.strip().str.lower()

    if period_col == "year":
        period_keys = sorted(work[period_col].unique().tolist(), key=lambda p: int(p))
    elif period_order:
        period_keys = sorted(
            work[period_col].dropna().unique().tolist(),
            key=lambda p: period_order.get(str(p).lower(), 99),
        )
    else:
        period_keys = sorted(work[period_col].dropna().unique().tolist())

    rows: list[dict] = []
    for period in period_keys:
        period_df = work[work[period_col].astype(str) == str(period)]
        market_ton = float(period_df["volume_ton"].sum())
        for cid in customer_ids:
            vol = _customer_volume_in_df(period_df, customer_col, cid)
            share_pct = (vol / market_ton * 100) if market_ton > 0 else 0.0
            rows.append(
                {
                    "period": str(period),
                    "customer_id": cid,
                    "volume_ton": vol,
                    "market_ton": market_ton,
                    "share_pct": round(share_pct, 1),
                }
            )

    metrics_df = pd.DataFrame(rows)
    period_labels = [_format_compare_period_label(p, period_col) for p in period_keys]
    return metrics_df, period_keys, period_labels


def _customer_series_by_period(
    metrics_df: pd.DataFrame,
    *,
    customer_id: str,
    period_keys: list[str],
    value_col: str,
) -> list[float]:
    sub = metrics_df[metrics_df["customer_id"] == customer_id].set_index("period")
    values: list[float] = []
    for period in period_keys:
        key = str(period)
        if key in sub.index:
            values.append(float(sub.loc[key, value_col]))
        else:
            values.append(0.0)
    return values


def build_customer_compare_color_map(customer_ids: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for i, cid in enumerate(customer_ids):
        result[str(cid)] = CUSTOMER_COMPARE_FALLBACK_COLORS[i % len(CUSTOMER_COMPARE_FALLBACK_COLORS)]
    return result


def _format_compare_customer_volume_chart_title(
    *,
    material_type: str,
    sale_channel: str,
    period_mode: str,
    year_int: int,
    period_caption: str,
) -> str:
    mt_label = str(material_type).strip()
    channel = str(sale_channel).strip()
    if period_mode == "Yearly":
        return f"Compare customer volume · {mt_label} · {period_caption}"
    if period_mode == "Quarterly":
        return f"Customer Volume Comparison: {mt_label} vs. {channel} (Quarterly {year_int})"
    if period_mode == "Monthly":
        return f"Customer Volume Comparison: {mt_label} vs. {channel} (Monthly {year_int})"
    return f"Compare customer volume · {mt_label} · {period_caption}"


def _format_compare_customer_share_chart_title(
    *,
    material_type: str,
    sale_channel: str,
    period_mode: str,
    year_int: int,
    period_caption: str,
) -> str:
    mt_label = str(material_type).strip()
    channel = str(sale_channel).strip()
    if period_mode == "Yearly":
        return f"Compare customer market share · {mt_label} · {period_caption}"
    if period_mode == "Quarterly":
        return f"Customer Market Share Comparison: {mt_label} vs. {channel} (Quarterly {year_int})"
    if period_mode == "Monthly":
        return f"Customer Market Share Comparison: {mt_label} vs. {channel} (Monthly {year_int})"
    return f"Compare customer market share · {mt_label} · {period_caption}"


def render_customer_compare_volume_chart(
    metrics_df: pd.DataFrame,
    *,
    customer_ids: list[str],
    id_to_name: dict[str, str],
    period_labels: list[str],
    period_keys: list[str],
    material_type: str,
    period_mode: str,
    year_int: int,
    sale_channel: str,
    period_caption: str,
    empty_message: str = "No volume data for the selected customers.",
) -> None:
    import plotly.graph_objects as go

    title = _format_compare_customer_volume_chart_title(
        material_type=material_type,
        sale_channel=sale_channel,
        period_mode=period_mode,
        year_int=year_int,
        period_caption=period_caption,
    )
    chart_card_title(title, large=True)
    if metrics_df.empty or not period_labels:
        st.info(empty_message)
        return

    fig = go.Figure()
    compare_colors = build_customer_compare_color_map(customer_ids)
    for cid in customer_ids:
        display_name = format_customer_display_name(id_to_name.get(cid, cid))
        vols = _customer_series_by_period(
            metrics_df, customer_id=cid, period_keys=period_keys, value_col="volume_ton"
        )
        fig.add_trace(
            go.Bar(
                x=period_labels,
                y=vols,
                name=display_name,
                marker_color=compare_colors.get(str(cid), CHART["blue"]),
                hovertemplate="%{x}<br>%{fullData.name}: %{y:,.1f} ton<extra></extra>",
            )
        )

    fig.update_layout(
        barmode="group",
        bargap=0.18,
        bargroupgap=0.08,
        height=420,
        margin=dict(l=20, r=20, t=12, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#E5E7EB"),
        template="plotly_dark",
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.18,
            xanchor="center",
            x=0.5,
            font=dict(size=11, color="#E5E7EB"),
        ),
        xaxis=dict(title="", showgrid=False),
        yaxis=dict(title="Volume (ton)", gridcolor="#374151", tickformat=","),
    )
    st.plotly_chart(fig, use_container_width=True, key="cust_compare_volume_chart")


def render_customer_compare_share_chart(
    metrics_df: pd.DataFrame,
    *,
    customer_ids: list[str],
    id_to_name: dict[str, str],
    period_labels: list[str],
    period_keys: list[str],
    material_type: str,
    period_mode: str,
    year_int: int,
    sale_channel: str,
    period_caption: str,
    empty_message: str = "No market share data for the selected customers.",
) -> None:
    import plotly.graph_objects as go

    title = _format_compare_customer_share_chart_title(
        material_type=material_type,
        sale_channel=sale_channel,
        period_mode=period_mode,
        year_int=year_int,
        period_caption=period_caption,
    )
    chart_card_title(title, large=True)
    if metrics_df.empty or not period_labels:
        st.info(empty_message)
        return

    fig = go.Figure()
    compare_colors = build_customer_compare_color_map(customer_ids)
    for cid in customer_ids:
        display_name = format_customer_display_name(id_to_name.get(cid, cid))
        shares = _customer_series_by_period(
            metrics_df, customer_id=cid, period_keys=period_keys, value_col="share_pct"
        )
        line_color = compare_colors.get(str(cid), CHART["green"])
        fig.add_trace(
            go.Scatter(
                x=period_labels,
                y=shares,
                name=display_name,
                mode="lines+markers",
                line=dict(color=line_color, width=2.5),
                marker=dict(size=8, color=line_color),
                hovertemplate="%{x}<br>%{fullData.name}: %{y:.1f}%<extra></extra>",
            )
        )

    y_max = max(
        [
            v
            for cid in customer_ids
            for v in _customer_series_by_period(
                metrics_df, customer_id=cid, period_keys=period_keys, value_col="share_pct"
            )
        ],
        default=0.0,
    )
    fig.update_layout(
        height=380,
        margin=dict(l=20, r=20, t=12, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#E5E7EB"),
        template="plotly_dark",
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.2,
            xanchor="center",
            x=0.5,
            font=dict(size=11, color="#E5E7EB"),
        ),
        xaxis=dict(title="", showgrid=False),
        yaxis=dict(
            title="Market share (%)",
            gridcolor="#374151",
            ticksuffix="%",
            range=[0, max(y_max * 1.2, 10.0)],
        ),
    )
    st.plotly_chart(fig, use_container_width=True, key="cust_compare_share_chart")


def render_customer_compare_dashboard(
    df: pd.DataFrame,
    *,
    material_type: str,
    customer_ids: list[str],
    id_to_name: dict[str, str],
    type_col: str,
    customer_col: str,
    period_mode: str,
    year_int: int,
    sale_channel: str,
) -> None:
    if period_mode == "Yearly":
        period_col = "year"
        period_order = None
        year_filter = None
        period_caption = f"{sale_channel} · all years"
    elif period_mode == "Quarterly":
        period_col = "quarter"
        period_order = QUARTER_ORDER
        year_filter = year_int
        period_caption = f"{sale_channel} · {year_int}"
    else:
        period_col = "month"
        period_order = MONTH_ORDER
        year_filter = year_int
        period_caption = f"{sale_channel} · {year_int}"

    metrics_df, period_keys, period_labels = build_multi_customer_period_metrics(
        df,
        material_type=material_type,
        customer_ids=customer_ids,
        type_col=type_col,
        customer_col=customer_col,
        period_col=period_col,
        period_order=period_order,
        year_filter=year_filter,
    )
    if metrics_df.empty:
        st.warning("No comparison data for the selected filters and customers.")
        return

    render_customer_compare_volume_chart(
        metrics_df,
        customer_ids=customer_ids,
        id_to_name=id_to_name,
        period_labels=period_labels,
        period_keys=period_keys,
        material_type=material_type,
        period_mode=period_mode,
        year_int=year_int,
        sale_channel=sale_channel,
        period_caption=period_caption,
    )
    render_customer_compare_share_chart(
        metrics_df,
        customer_ids=customer_ids,
        id_to_name=id_to_name,
        period_labels=period_labels,
        period_keys=period_keys,
        material_type=material_type,
        period_mode=period_mode,
        year_int=year_int,
        sale_channel=sale_channel,
        period_caption=period_caption,
    )


# ── Tab 2: Single supplier — top customers (always sidebar year) ─────────────


def build_supplier_top_customers_data(
    df: pd.DataFrame,
    *,
    top_n: int,
    others_label: str = "Others",
) -> tuple[pd.DataFrame, int]:
    """
    Rank customers by volume within a supplier-period scope.
    Returns (chart_df with customer_label, volume_ton, share_pct), total_unique_customers.
    Includes an Others row when customers exceed top_n.
    Share is % of total supplier volume in scope.
    """
    empty = pd.DataFrame(columns=["customer_label", "volume_ton", "share_pct"])
    if df.empty or "volume_ton" not in df.columns:
        return empty, 0

    work = df.copy()
    group_col = "customer_id" if "customer_id" in work.columns else "customer_name"
    name_col = "customer_name" if "customer_name" in work.columns else group_col
    if group_col not in work.columns:
        return empty, 0

    work[group_col] = work[group_col].fillna("").astype(str).str.strip()
    work = work[work[group_col] != ""]
    if work.empty:
        return empty, 0

    grouped = (
        work.groupby(group_col, dropna=False)["volume_ton"]
        .sum()
        .reset_index()
        .sort_values("volume_ton", ascending=False)
    )
    n_customers = len(grouped)
    total = float(grouped["volume_ton"].sum())
    if total <= 0:
        return empty, n_customers

    if group_col == "customer_id" and name_col in work.columns:
        name_lookup = (
            work.groupby(group_col)[name_col]
            .agg(lambda s: max(s.dropna().astype(str).tolist(), key=len, default=""))
            .to_dict()
        )
        grouped["customer_label"] = grouped[group_col].map(
            lambda cid: format_customer_display_name(name_lookup.get(cid, cid))
        )
    else:
        grouped["customer_label"] = grouped[group_col].map(format_customer_display_name)

    top = grouped.head(top_n).copy()
    top["share_pct"] = (top["volume_ton"] / total * 100).round(1)

    others_vol = float(grouped.iloc[top_n:]["volume_ton"].sum()) if n_customers > top_n else 0.0
    rows = top[["customer_label", "volume_ton", "share_pct"]].to_dict("records")
    if others_vol > 0:
        rows.append(
            {
                "customer_label": others_label,
                "volume_ton": others_vol,
                "share_pct": round(others_vol / total * 100, 1),
            }
        )

    return pd.DataFrame(rows), n_customers


def render_supplier_top_customers_chart(
    df: pd.DataFrame,
    *,
    supplier: str,
    material_type: str,
    sale_channel: str,
    year_int: int,
    top_n: int,
    side_panel: bool = False,
    empty_message: str = "No customer volume for this supplier and year.",
) -> None:
    import plotly.graph_objects as go

    from config.settings import SUPPLIER_TOP_CUSTOMERS_OTHERS_LABEL

    supplier_name = format_supplier_display_name(supplier)
    mt_label = str(material_type).strip()
    chart_df, n_customers = build_supplier_top_customers_data(
        df,
        top_n=top_n,
        others_label=SUPPLIER_TOP_CUSTOMERS_OTHERS_LABEL,
    )

    if side_panel:
        chart_card_title(f"Top customers · Year {year_int}", large=True)
        st.caption(
            f"{supplier_name} · {mt_label} · {sale_channel} · "
            f"{n_customers:,} customers · Top {top_n}"
        )
    else:
        chart_card_title(
            f"Top customers · {supplier_name} · {mt_label} · {sale_channel} · Year {year_int}",
            large=True,
        )
        st.caption(f"{n_customers:,} customers in {year_int} · Top {top_n} shown")

    if chart_df.empty:
        st.info(empty_message)
        return

    labels = [
        format_customer_display_name(lbl)
        for lbl in chart_df["customer_label"].astype(str).tolist()
    ]
    colors = [
        CUSTOMER_COMPARE_FALLBACK_COLORS[i % len(CUSTOMER_COMPARE_FALLBACK_COLORS)]
        if str(raw) != SUPPLIER_TOP_CUSTOMERS_OTHERS_LABEL
        else "#4B5563"
        for i, raw in enumerate(chart_df["customer_label"].astype(str).tolist())
    ]

    fig = go.Figure(
        go.Bar(
            x=chart_df["volume_ton"].astype(float).tolist(),
            y=labels,
            orientation="h",
            marker_color=colors,
            text=[
                f"{v:,.1f} ton · {p:.1f}%"
                for v, p in zip(chart_df["volume_ton"], chart_df["share_pct"])
            ],
            textposition="inside" if side_panel else "outside",
            textfont=dict(color="#E5E7EB", size=10 if side_panel else 11),
            hovertemplate="%{y}<br>Volume: %{x:,.1f} ton<extra></extra>",
        )
    )
    x_max = float(chart_df["volume_ton"].max()) * (1.15 if side_panel else 1.3) if not chart_df.empty else 1.0
    chart_height = 460 if side_panel else max(280, 48 * len(labels) + 80)
    fig.update_layout(
        height=chart_height,
        margin=dict(l=12, r=12 if side_panel else 60, t=12, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#E5E7EB"),
        template="plotly_dark",
        showlegend=False,
        xaxis=dict(title="Volume (ton)", range=[0, x_max], tickformat=","),
        yaxis=dict(title="", autorange="reversed"),
    )
    st.plotly_chart(fig, use_container_width=True, key="sup_top_customers_chart")


def build_supplier_top_salers_data(
    df: pd.DataFrame,
    *,
    top_n: int,
    others_label: str = "Others",
) -> tuple[pd.DataFrame, int]:
    """
    Rank salers (trading partners) by volume within a supplier-period scope.
    Returns (chart_df with saler_label, volume_ton, share_pct), total_unique_salers.
    """
    empty = pd.DataFrame(columns=["saler_label", "volume_ton", "share_pct"])
    if df.empty or "volume_ton" not in df.columns or "saler" not in df.columns:
        return empty, 0

    work = df.copy()
    work["saler"] = work["saler"].fillna("").astype(str).str.strip()
    work = work[work["saler"] != ""]
    if work.empty:
        return empty, 0

    grouped = (
        work.groupby("saler", dropna=False)["volume_ton"]
        .sum()
        .reset_index()
        .sort_values("volume_ton", ascending=False)
    )
    n_salers = len(grouped)
    total = float(grouped["volume_ton"].sum())
    if total <= 0:
        return empty, n_salers

    grouped["saler_label"] = grouped["saler"].map(format_saler_display_name)
    top = grouped.head(top_n).copy()
    top["share_pct"] = (top["volume_ton"] / total * 100).round(1)

    others_vol = float(grouped.iloc[top_n:]["volume_ton"].sum()) if n_salers > top_n else 0.0
    rows = top[["saler_label", "volume_ton", "share_pct"]].to_dict("records")
    if others_vol > 0:
        rows.append(
            {
                "saler_label": others_label,
                "volume_ton": others_vol,
                "share_pct": round(others_vol / total * 100, 1),
            }
        )

    return pd.DataFrame(rows), n_salers


def render_supplier_top_salers_chart(
    df: pd.DataFrame,
    *,
    supplier: str,
    material_type: str,
    sale_channel: str,
    year_int: int,
    top_n: int,
    side_panel: bool = False,
    chart_key: str = "sup_top_salers_chart",
    empty_message: str = "No saler volume for this supplier and year.",
) -> None:
    """Top salers by volume for sidebar year — same layout as Top customers."""
    import plotly.graph_objects as go

    from config.settings import SUPPLIER_TOP_CUSTOMERS_OTHERS_LABEL

    supplier_name = format_supplier_display_name(supplier)
    mt_label = str(material_type).strip()
    chart_df, n_salers = build_supplier_top_salers_data(
        df,
        top_n=top_n,
        others_label=SUPPLIER_TOP_CUSTOMERS_OTHERS_LABEL,
    )

    if side_panel:
        chart_card_title(f"Top salers · Year {year_int}", large=True)
        st.caption(
            f"{supplier_name} · {mt_label} · {sale_channel} · "
            f"{n_salers:,} salers · Top {top_n}"
        )
    else:
        chart_card_title(
            f"Top salers · {supplier_name} · {mt_label} · {sale_channel} · Year {year_int}",
            large=True,
        )
        st.caption(f"{n_salers:,} salers in {year_int} · Top {top_n} shown")

    if chart_df.empty:
        st.info(empty_message)
        return

    labels = [
        format_saler_display_name(lbl)
        for lbl in chart_df["saler_label"].astype(str).tolist()
    ]
    colors = [
        CUSTOMER_COMPARE_FALLBACK_COLORS[i % len(CUSTOMER_COMPARE_FALLBACK_COLORS)]
        if str(raw) != SUPPLIER_TOP_CUSTOMERS_OTHERS_LABEL
        else "#4B5563"
        for i, raw in enumerate(chart_df["saler_label"].astype(str).tolist())
    ]

    fig = go.Figure(
        go.Bar(
            x=chart_df["volume_ton"].astype(float).tolist(),
            y=labels,
            orientation="h",
            marker_color=colors,
            text=[
                f"{v:,.1f} ton · {p:.1f}%"
                for v, p in zip(chart_df["volume_ton"], chart_df["share_pct"])
            ],
            textposition="inside" if side_panel else "outside",
            textfont=dict(color="#E5E7EB", size=10 if side_panel else 11),
            hovertemplate="%{y}<br>Volume: %{x:,.1f} ton<extra></extra>",
        )
    )
    x_max = float(chart_df["volume_ton"].max()) * (1.15 if side_panel else 1.3) if not chart_df.empty else 1.0
    chart_height = 460 if side_panel else max(280, 48 * len(labels) + 80)
    fig.update_layout(
        height=chart_height,
        margin=dict(l=12, r=12 if side_panel else 60, t=12, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#E5E7EB"),
        template="plotly_dark",
        showlegend=False,
        xaxis=dict(title="Volume (ton)", range=[0, x_max], tickformat=","),
        yaxis=dict(title="", autorange="reversed"),
    )
    st.plotly_chart(fig, use_container_width=True, key=chart_key)


def _customer_rank_bar_colors(labels: list[str], *, others_label: str) -> list[str]:
    """Blue gradient for ranked customers; neutral grey for Others."""
    colors: list[str] = []
    rank_idx = 0
    for lbl in labels:
        if str(lbl) == others_label:
            colors.append(CUSTOMER_RANK_OTHERS_COLOR)
        else:
            colors.append(CUSTOMER_RANK_BAR_BLUES[min(rank_idx, len(CUSTOMER_RANK_BAR_BLUES) - 1)])
            rank_idx += 1
    return colors


def build_customer_suppliers_ranked_data(
    df: pd.DataFrame,
    *,
    supplier_col: str,
) -> tuple[pd.DataFrame, int]:
    """Rank all suppliers by volume for a customer-period scope. Share = % of customer volume."""
    empty = pd.DataFrame(columns=["supplier_label", "volume_ton", "share_pct"])
    if df.empty or supplier_col not in df.columns or "volume_ton" not in df.columns:
        return empty, 0

    work = df.copy()
    work[supplier_col] = work[supplier_col].fillna("").astype(str).str.strip()
    work = work[work[supplier_col] != ""]
    if work.empty:
        return empty, 0

    grouped = (
        work.groupby(supplier_col, dropna=False)["volume_ton"]
        .sum()
        .reset_index()
        .sort_values("volume_ton", ascending=False)
    )
    n_suppliers = len(grouped)
    total = float(grouped["volume_ton"].sum())
    if total <= 0:
        return empty, n_suppliers

    grouped["supplier_label"] = grouped[supplier_col].map(format_supplier_display_name)
    grouped["share_pct"] = (grouped["volume_ton"] / total * 100).round(1)
    return grouped[["supplier_label", "volume_ton", "share_pct"]].copy(), n_suppliers


def _ranked_bar_chart_height(n_bars: int, *, cap: int | None = 420) -> int:
    height = max(200, 56 + 44 * n_bars)
    if cap is not None:
        height = min(cap, height)
    return height


def build_customer_top_suppliers_data(
    df: pd.DataFrame,
    *,
    supplier_col: str,
    top_n: int,
    others_label: str = "Others",
) -> tuple[pd.DataFrame, int]:
    """Rank suppliers by volume for a customer-period scope. Share = % of customer volume."""
    empty = pd.DataFrame(columns=["supplier_label", "volume_ton", "share_pct"])
    if df.empty or supplier_col not in df.columns or "volume_ton" not in df.columns:
        return empty, 0

    work = df.copy()
    work[supplier_col] = work[supplier_col].fillna("").astype(str).str.strip()
    work = work[work[supplier_col] != ""]
    if work.empty:
        return empty, 0

    grouped = (
        work.groupby(supplier_col, dropna=False)["volume_ton"]
        .sum()
        .reset_index()
        .sort_values("volume_ton", ascending=False)
    )
    n_suppliers = len(grouped)
    total = float(grouped["volume_ton"].sum())
    if total <= 0:
        return empty, n_suppliers

    grouped["supplier_label"] = grouped[supplier_col].map(format_supplier_display_name)
    top = grouped.head(top_n).copy()
    top["share_pct"] = (top["volume_ton"] / total * 100).round(1)

    others_vol = float(grouped.iloc[top_n:]["volume_ton"].sum()) if n_suppliers > top_n else 0.0
    rows = top[["supplier_label", "volume_ton", "share_pct"]].to_dict("records")
    if others_vol > 0:
        rows.append(
            {
                "supplier_label": others_label,
                "volume_ton": others_vol,
                "share_pct": round(others_vol / total * 100, 1),
            }
        )
    return pd.DataFrame(rows), n_suppliers


def _render_period_ranked_horizontal_bars(
    *,
    chart_df: pd.DataFrame,
    entity_label_col: str,
    others_label: str,
    format_name,
    chart_title: str,
    footnote: str,
    chart_key: str,
    empty_message: str,
    max_chart_height: int | None = 420,
) -> None:
    """Shared horizontal ranked bar renderer (Tab 2 customers / Tab 3 suppliers)."""
    import plotly.graph_objects as go

    chart_card_title(chart_title, large=True)
    chart_footnote(footnote)

    if chart_df.empty:
        st.info(empty_message)
        return

    raw_labels = chart_df[entity_label_col].astype(str).tolist()
    display_labels: list[str] = []
    rank = 0
    for lbl in raw_labels:
        if lbl == others_label:
            display_labels.append(others_label)
        else:
            rank += 1
            display_labels.append(f"#{rank}  {format_name(lbl, max_len=22)}")

    colors = _customer_rank_bar_colors(raw_labels, others_label=others_label)
    volumes = chart_df["volume_ton"].astype(float).tolist()
    shares = chart_df["share_pct"].astype(float).tolist()
    max_vol = float(max(volumes)) if volumes else 0.0
    inside_text = [
        f"{v:,.0f}" if max_vol > 0 and v >= max_vol * 0.07 else ""
        for v in volumes
    ]

    fig = go.Figure(
        go.Bar(
            x=volumes,
            y=display_labels,
            orientation="h",
            marker=dict(
                color=colors,
                line=dict(color="rgba(255, 255, 255, 0.12)", width=0.8),
                cornerradius=5,
            ),
            text=inside_text,
            textposition="inside",
            insidetextanchor="middle",
            textfont=dict(color="#FFFFFF", size=11, family="Segoe UI"),
            customdata=shares,
            hovertemplate=(
                "%{y}<br>Volume: %{x:,.1f} ton<br>Share: %{customdata:.1f}%<extra></extra>"
            ),
            hoverlabel=PERIOD_CUSTOMER_VOLUME_HOVERLABEL,
        )
    )
    x_max = max_vol * 1.12 if max_vol > 0 else 1.0
    n_bars = len(display_labels)
    chart_height = _ranked_bar_chart_height(n_bars, cap=max_chart_height)
    fig.update_layout(
        height=chart_height,
        margin=dict(l=8, r=16, t=16, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#E5E7EB", family="Segoe UI", size=12),
        template="plotly_dark",
        showlegend=False,
        hovermode="closest",
        hoverlabel=PERIOD_CUSTOMER_VOLUME_HOVERLABEL,
        bargap=0.22,
    )
    fig.update_xaxes(
        title_text="Volume (ton)",
        title_font=dict(size=11, color="#9CA3AF"),
        range=[0, x_max],
        tickformat=",",
        gridcolor="rgba(55, 65, 81, 0.45)",
        zeroline=False,
        tickfont=dict(size=11, color="#9CA3AF"),
        linewidth=1,
        linecolor="#4B5563",
    )
    fig.update_yaxes(
        title_text="",
        autorange="reversed",
        showgrid=False,
        tickfont=dict(size=11, color="#D1D5DB"),
        linewidth=1,
        linecolor="#4B5563",
    )
    st.plotly_chart(fig, use_container_width=True, key=chart_key)


def render_supplier_period_customer_volume_chart(
    df: pd.DataFrame,
    *,
    supplier: str,
    material_type: str,
    sale_channel: str,
    year_int: int,
    period_label: str,
    top_n: int,
    chart_key: str,
    empty_message: str = "No customer volume for this supplier and period.",
) -> None:
    """Horizontal ranked bars: customer volume for selected quarter/month."""
    from config.settings import SUPPLIER_TOP_CUSTOMERS_OTHERS_LABEL

    supplier_name = format_supplier_display_name(supplier)
    mt_label = str(material_type).strip()
    chart_df, n_customers = build_supplier_top_customers_data(
        df,
        top_n=top_n,
        others_label=SUPPLIER_TOP_CUSTOMERS_OTHERS_LABEL,
    )
    _render_period_ranked_horizontal_bars(
        chart_df=chart_df,
        entity_label_col="customer_label",
        others_label=SUPPLIER_TOP_CUSTOMERS_OTHERS_LABEL,
        format_name=format_customer_display_name,
        chart_title=f"Customer volume · {period_label} {year_int}",
        footnote=(
            f"{supplier_name} · {mt_label} · {sale_channel} · "
            f"{n_customers:,} customers · Top {top_n}"
        ),
        chart_key=chart_key,
        empty_message=empty_message,
    )


def _customer_group_column(df: pd.DataFrame) -> str | None:
    if "customer_id" in df.columns:
        return "customer_id"
    if "customer_name" in df.columns:
        return "customer_name"
    return None


def _order_period_keys(period_keys: list[str], period_col: str) -> list[str]:
    if period_col == "year":
        numeric: list[int] = []
        for p in period_keys:
            try:
                numeric.append(int(float(str(p).strip())))
            except (ValueError, TypeError):
                continue
        return [str(y) for y in sorted(set(numeric))]
    if period_col == "quarter":
        return [q for q in ("q1", "q2", "q3", "q4") if q in period_keys]
    if period_col == "month":
        return sorted(period_keys, key=lambda m: MONTH_ORDER.get(str(m).lower(), 99))
    return sorted(period_keys)


def build_supplier_count_data(
    df: pd.DataFrame,
    *,
    supplier: str,
    material_type: str,
    type_col: str,
    supplier_col: str,
    period_col: str,
    year_int: int | None = None,
) -> pd.DataFrame:
    """Count unique customers by period for one supplier and material type."""
    if df.empty or supplier_col not in df.columns:
        return pd.DataFrame(columns=[period_col, "customer_count"])

    mt = str(material_type).strip()
    base = filter_by_material_type(df, mt, type_col=type_col)
    if base.empty:
        return pd.DataFrame(columns=[period_col, "customer_count"])

    if year_int is not None and "year" in base.columns:
        base = base[base["year"] == year_int].copy()

    sel = str(supplier).strip().casefold()
    mask = base[supplier_col].astype(str).str.strip().str.casefold() == sel
    base = base[mask].copy()
    if base.empty:
        return pd.DataFrame(columns=[period_col, "customer_count"])

    group_col = _customer_group_column(base)
    if group_col is None:
        return pd.DataFrame(columns=[period_col, "customer_count"])

    base[group_col] = base[group_col].fillna("").astype(str).str.strip()
    base = base[base[group_col] != ""].copy()
    if base.empty:
        return pd.DataFrame(columns=[period_col, "customer_count"])

    if period_col not in base.columns:
        return pd.DataFrame(columns=[period_col, "customer_count"])

    work = base.copy()
    work[period_col] = work[period_col].astype(str).str.strip().str.lower()
    if work[period_col].dropna().empty:
        return pd.DataFrame(columns=[period_col, "customer_count"])

    grouped = (
        work.groupby([period_col, group_col], dropna=False)
        .size()
        .reset_index(name="row_count")
        .groupby(period_col, dropna=False)[group_col]
        .nunique()
        .reset_index(name="customer_count")
    )

    if period_col == "year":
        grouped[period_col] = grouped[period_col].apply(
            lambda y: str(int(float(y))) if pd.notna(y) and str(y).strip() not in ("", "nan") else ""
        )
        grouped = grouped[grouped[period_col] != ""].copy()

    period_keys = grouped[period_col].astype(str).tolist()
    ordered_keys = _order_period_keys(period_keys, period_col)
    grouped[period_col] = grouped[period_col].astype(str)
    ordered = grouped.set_index(period_col).reindex(ordered_keys).reset_index()
    ordered["customer_count"] = ordered["customer_count"].fillna(0).astype(int)
    return ordered[[period_col, "customer_count"]]


def _filter_supplier_customer_scope(
    df: pd.DataFrame,
    *,
    supplier: str,
    material_type: str,
    type_col: str,
    supplier_col: str,
) -> tuple[pd.DataFrame, str | None]:
    """Rows for one supplier + material type (sale channel already applied upstream)."""
    if df.empty or supplier_col not in df.columns:
        return pd.DataFrame(), None

    mt = str(material_type).strip()
    base = filter_by_material_type(df, mt, type_col=type_col)
    if base.empty:
        return pd.DataFrame(), None

    sel = str(supplier).strip().casefold()
    mask = base[supplier_col].astype(str).str.strip().str.casefold() == sel
    base = base[mask].copy()
    if base.empty:
        return pd.DataFrame(), None

    group_col = _customer_group_column(base)
    if group_col is None:
        return pd.DataFrame(), None

    base[group_col] = base[group_col].fillna("").astype(str).str.strip()
    base = base[base[group_col] != ""].copy()
    return base, group_col


def _normalized_buyer_set(frame: pd.DataFrame, group_col: str) -> set[str]:
    if frame.empty:
        return set()
    vals = frame[group_col].dropna().astype(str).str.strip()
    vals = vals[vals != ""]
    if group_col == "customer_id":
        return {normalize_customer_id(v) for v in vals if normalize_customer_id(v)}
    return set(vals.tolist())


def _period_display_label(period_col: str, period_key: str) -> str:
    if period_col == "year":
        return str(period_key)
    if period_col == "quarter":
        return str(period_key).upper()
    if period_col == "month":
        month_num = MONTH_ORDER.get(str(period_key).lower())
        if month_num and 1 <= month_num <= 12:
            return MONTH_DISPLAY[month_num - 1]
        return str(period_key).title()
    return str(period_key)


def build_supplier_customer_new_current_data(
    df: pd.DataFrame,
    *,
    supplier: str,
    material_type: str,
    type_col: str,
    supplier_col: str,
    period_col: str,
    year_int: int | None = None,
) -> pd.DataFrame:
    """
    Cumulative current vs new unique customers by period.

    Yearly: each year builds on all prior years in the dataset.
    Quarterly/Monthly (sidebar year): base before Q1/Jan = all buyers in years < year_int,
    then cumulative within that year.
    """
    empty = pd.DataFrame(
        columns=[period_col, "current_count", "new_count", "customer_count", "period_label"]
    )
    scope, group_col = _filter_supplier_customer_scope(
        df,
        supplier=supplier,
        material_type=material_type,
        type_col=type_col,
        supplier_col=supplier_col,
    )
    if scope.empty or group_col is None or period_col not in scope.columns:
        return empty

    work = scope.copy()
    if "year" in work.columns:
        work["_year_int"] = pd.to_numeric(work["year"], errors="coerce")

    work[period_col] = work[period_col].astype(str).str.strip().str.lower()
    rows: list[dict] = []
    cumulative: set[str] = set()

    if period_col == "year":
        if "_year_int" not in work.columns:
            return empty
        years = sorted(work["_year_int"].dropna().astype(int).unique().tolist())
        period_keys = [str(y) for y in years]
        for year_key in period_keys:
            y = int(year_key)
            buyers = _normalized_buyer_set(work[work["_year_int"] == y], group_col)
            current = buyers & cumulative
            new = buyers - cumulative
            rows.append(
                {
                    period_col: year_key,
                    "current_count": len(current),
                    "new_count": len(new),
                    "customer_count": len(buyers),
                    "period_label": _period_display_label(period_col, year_key),
                }
            )
            cumulative |= buyers
    elif period_col == "quarter":
        if year_int is None or "_year_int" not in work.columns:
            return empty
        cumulative = _normalized_buyer_set(work[work["_year_int"] < year_int], group_col)
        year_slice = work[work["_year_int"] == year_int].copy()
        for q in QUARTER_ORDER:
            buyers = _normalized_buyer_set(year_slice[year_slice[period_col] == q], group_col)
            current = buyers & cumulative
            new = buyers - cumulative
            rows.append(
                {
                    period_col: q,
                    "current_count": len(current),
                    "new_count": len(new),
                    "customer_count": len(buyers),
                    "period_label": _period_display_label(period_col, q),
                }
            )
            cumulative |= buyers
    elif period_col == "month":
        if year_int is None or "_year_int" not in work.columns:
            return empty
        cumulative = _normalized_buyer_set(work[work["_year_int"] < year_int], group_col)
        year_slice = work[work["_year_int"] == year_int].copy()
        for m in MONTH_ORDER:
            buyers = _normalized_buyer_set(year_slice[year_slice[period_col] == m], group_col)
            current = buyers & cumulative
            new = buyers - cumulative
            rows.append(
                {
                    period_col: m,
                    "current_count": len(current),
                    "new_count": len(new),
                    "customer_count": len(buyers),
                    "period_label": _period_display_label(period_col, m),
                }
            )
            cumulative |= buyers
    else:
        return empty

    if not rows:
        return empty

    out = pd.DataFrame(rows)
    out["current_count"] = out["current_count"].astype(int)
    out["new_count"] = out["new_count"].astype(int)
    out["customer_count"] = out["customer_count"].astype(int)
    return out


def render_supplier_customer_new_current_stacked_chart(
    df: pd.DataFrame,
    *,
    period_col: str,
    title: str,
    x_title: str,
    empty_message: str = "No customer count data.",
    chart_key: str | None = None,
) -> None:
    """Stacked bar: repeat vs new-to-supplier unique customers per period."""
    chart_card_title(title, large=True)
    if df.empty or df[["current_count", "new_count"]].sum().sum() == 0:
        st.info(empty_message)
        return

    import plotly.graph_objects as go

    labels = df["period_label"].astype(str).tolist()
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            name="Repeat buyer",
            x=labels,
            y=df["current_count"].tolist(),
            marker_color=CHART["blue"],
        )
    )
    fig.add_trace(
        go.Bar(
            name="New to this supplier",
            x=labels,
            y=df["new_count"].tolist(),
            marker_color=CHART["green"],
        )
    )
    fig.update_layout(
        barmode="stack",
        height=360,
        margin=dict(l=20, r=20, t=36, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        template="plotly_dark",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        font=dict(color="#E5E7EB"),
        xaxis=dict(
            title=x_title,
            categoryorder="array",
            categoryarray=labels,
        ),
        yaxis=dict(title="Customers", gridcolor="#374151"),
    )
    fig.update_xaxes(showgrid=False)
    st.plotly_chart(fig, use_container_width=True, key=chart_key)
    chart_footnote(
        "**Repeat buyer**: customer who already purchased from **this supplier** in an earlier "
        "period (same material type and sale channel as selected above). "
        "**New to this supplier**: customer's **first purchase from this supplier** in the filtered "
        "data — purchases from other suppliers are not counted. "
        "Quarterly/monthly: buyers before Q1/Jan include all prior years."
    )


def render_supplier_count_bar_chart(
    df: pd.DataFrame,
    *,
    period_col: str,
    title: str,
    x_title: str,
    empty_message: str = "No customer count data.",
) -> None:
    chart_card_title(title, large=True)
    if df.empty:
        st.info(empty_message)
        return

    import plotly.express as px

    chart_df = df.copy()
    chart_df["period_label"] = chart_df[period_col].astype(str).str.upper()
    fig = px.bar(
        chart_df,
        x="period_label",
        y="customer_count",
        title=None,
        labels={"period_label": x_title, "customer_count": "Customers"},
        color_discrete_sequence=[CHART["blue"]],
        template="plotly_dark",
    )
    fig.update_layout(
        height=360,
        margin=dict(l=20, r=20, t=36, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(categoryorder="array", categoryarray=chart_df["period_label"].tolist()),
        font=dict(color="#E5E7EB"),
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(title="Customers", gridcolor="#374151")
    st.plotly_chart(fig, use_container_width=True)


def render_customer_period_supplier_volume_chart(
    df: pd.DataFrame,
    *,
    customer_name: str,
    material_type: str,
    sale_channel: str,
    year_int: int,
    period_label: str,
    supplier_col: str,
    chart_key: str,
    empty_message: str = "No supplier volume for this customer and period.",
) -> None:
    """Horizontal ranked bars: all suppliers for selected quarter/month (Tab 3)."""
    display_customer = format_customer_display_name(customer_name)
    mt_label = str(material_type).strip()
    chart_df, n_suppliers = build_customer_suppliers_ranked_data(
        df,
        supplier_col=supplier_col,
    )
    _render_period_ranked_horizontal_bars(
        chart_df=chart_df,
        entity_label_col="supplier_label",
        others_label="",
        format_name=format_supplier_display_name,
        chart_title=f"Supplier volume · {period_label} {year_int}",
        footnote=(
            f"{display_customer} · {mt_label} · {sale_channel} · "
            f"{n_suppliers:,} suppliers"
        ),
        chart_key=chart_key,
        empty_message=empty_message,
        max_chart_height=None,
    )


def render_supplier_quarter_customer_volume_chart(
    df: pd.DataFrame,
    *,
    supplier: str,
    material_type: str,
    sale_channel: str,
    year_int: int,
    quarter: str,
    top_n: int,
    empty_message: str = "No customer volume for this supplier and quarter.",
) -> None:
    """Backward-compatible wrapper for quarterly customer volume chart."""
    quarter_label = str(quarter).upper()
    render_supplier_period_customer_volume_chart(
        df,
        supplier=supplier,
        material_type=material_type,
        sale_channel=sale_channel,
        year_int=year_int,
        period_label=quarter_label,
        top_n=top_n,
        chart_key=f"sup_quarter_customer_volume_{quarter_label}_{year_int}",
        empty_message=empty_message,
    )

