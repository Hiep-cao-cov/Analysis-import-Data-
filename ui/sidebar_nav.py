"""Sidebar navigation buttons (page switching)."""
from __future__ import annotations

import streamlit as st


def sidebar_nav_button(label: str, page_key: str, *, key_suffix: str = "") -> None:
    current = st.session_state.get("nav_page", "insights")
    is_active = current == page_key
    if st.button(
        label,
        key=f"nav_btn_{page_key}{key_suffix}",
        use_container_width=True,
        type="primary" if is_active else "secondary",
    ):
        if not is_active:
            st.session_state.nav_page = page_key
            st.rerun()
