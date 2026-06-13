"""Sidebar tools: detect and add customers missing from customer_list.csv."""
from __future__ import annotations

import io

import pandas as pd
import streamlit as st

from config.settings import CUSTOMER_LIST_FILE
from services.customer_name_service import (
    append_customers_to_list,
    apply_customer_short_names,
    find_unmapped_customers,
    reload_customer_short_name_map,
)
from ui.analysis_data import get_dataframe, set_dataframe


def _source_df_for_scan() -> pd.DataFrame | None:
    df = get_dataframe()
    if df is not None and not df.empty:
        return df
    return st.session_state.get("dash_pending_unmapped_scan")


def render_customer_list_panel() -> None:
    """Review customers not in customer_list.csv and add short names."""
    st.caption(
        f"Lookup file: `{CUSTOMER_LIST_FILE.name}` · "
        "Unmatched IDs keep the long company name in charts."
    )

    df = _source_df_for_scan()
    pending = st.session_state.get("dash_unmapped_customers")

    if st.button("Scan for new customers", key="cust_list_scan_btn", use_container_width=True):
        if df is None or df.empty:
            st.warning("Load or merge dataset first, then scan.")
        else:
            unmapped = find_unmapped_customers(df)
            st.session_state.dash_unmapped_customers = unmapped
            pending = unmapped

    if pending is None:
        return

    if pending.empty:
        st.success("All customers in the current dataset are in customer_list.csv.")
        return

    n_ids = len(pending)
    n_rows = int(pending["import_rows"].sum())
    st.warning(
        f"**{n_ids:,}** new customer(s) not in lookup "
        f"({n_rows:,} import rows). Add **short_name** below."
    )

    edited = st.data_editor(
        pending,
        column_config={
            "customer_id": st.column_config.TextColumn("customer_id", disabled=True),
            "full_name": st.column_config.TextColumn("Full name", disabled=True, width="large"),
            "import_rows": st.column_config.NumberColumn("Rows", disabled=True, format="%d"),
            "short_name": st.column_config.TextColumn(
                "short_name (required)",
                help="Short label used in charts and exports",
                width="medium",
            ),
        },
        hide_index=True,
        use_container_width=True,
        key="cust_list_editor",
        num_rows="fixed",
    )

    buf = io.StringIO()
    pending.to_csv(buf, index=False)
    st.download_button(
        "Download new-customer template (CSV)",
        buf.getvalue().encode("utf-8-sig"),
        file_name="new_customers_to_add.csv",
        mime="text/csv",
        use_container_width=True,
    )
    st.caption(
        "Fill **short_name** in Excel, then paste rows into customer_list.csv, "
        "or use **Save to customer list** below."
    )

    if st.button("Save to customer list", type="primary", key="cust_list_save_btn", use_container_width=True):
        to_save = edited.copy()
        to_save["short_name"] = to_save["short_name"].astype(str).str.strip()
        valid = to_save[
            (to_save["short_name"] != "")
            & (~to_save["short_name"].isin(["nan", "NaN", "None"]))
        ]
        if valid.empty:
            st.error("Enter at least one short_name before saving.")
            return

        try:
            added, skipped = append_customers_to_list(valid)
            reload_customer_short_name_map()

            live = get_dataframe()
            if live is not None and not live.empty:
                updated = apply_customer_short_names(live)
                source = st.session_state.get("dashboard_source", "dataset")
                set_dataframe(updated, source)

            remaining = find_unmapped_customers(get_dataframe() or df)
            st.session_state.dash_unmapped_customers = remaining

            msg = f"Added **{added:,}** customer(s) to `{CUSTOMER_LIST_FILE.name}`."
            if skipped:
                msg += f" Skipped **{skipped:,}** duplicate ID(s)."
            st.success(msg)
            if remaining.empty:
                st.info("All scanned customers are now mapped.")
            st.rerun()
        except Exception as exc:
            st.error(f"Could not update customer list: {exc}")
