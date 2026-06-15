"""Validate sidebar uploads match the selected MDI / TDI dataset."""
from __future__ import annotations

import pandas as pd

from config.settings import MDI_HS_CODES, TDI_HS_CODES


def normalize_analysis_dataset_mode(mode: str) -> str:
    m = str(mode).strip().upper()
    return "MDI" if m == "PMDI" else m


def _resolve_hs_column(df: pd.DataFrame) -> str | None:
    for col in df.columns:
        key = str(col).strip().lower().replace(" ", "").replace("_", "")
        if key == "hscode":
            return col
    return None


def detect_product_line_from_filename(file_name: str) -> str | None:
    """Infer MDI vs TDI from upload filename (e.g. predictions_pmdi_*, final_tdi_*)."""
    name = str(file_name).lower()
    if "pmdi" in name:
        return "MDI"
    if "tdi" in name:
        return "TDI"
    if "mdi" in name:
        return "MDI"
    return None


def detect_product_line_from_hs_codes(df: pd.DataFrame) -> str | None:
    """Infer MDI vs TDI from dominant HS codes in the upload."""
    col = _resolve_hs_column(df)
    if col is None or df.empty:
        return None
    codes = df[col].astype(str).str.replace(".", "", regex=False).str.strip()
    mdi_count = int(codes.isin(MDI_HS_CODES).sum())
    tdi_count = int(codes.isin(TDI_HS_CODES).sum())
    if mdi_count == 0 and tdi_count == 0:
        return None
    return "TDI" if tdi_count > mdi_count else "MDI"


def validate_upload_dataset_match(
    preview_df: pd.DataFrame,
    *,
    dataset_mode: str,
    file_name: str,
) -> str | None:
    """
    Return a user-facing error when the upload is not for the selected dataset.
    MDI dataset accepts MDI/PMDI HS rows; TDI dataset accepts TDI HS rows.
    """
    expected = normalize_analysis_dataset_mode(dataset_mode)
    hints: list[str] = []

    from_name = detect_product_line_from_filename(file_name)
    if from_name:
        hints.append(from_name)

    from_hs = detect_product_line_from_hs_codes(preview_df)
    if from_hs:
        hints.append(from_hs)

    if not hints:
        return None

    detected = from_hs or from_name
    if detected != expected:
        other = "TDI" if expected == "MDI" else "MDI"
        return (
            f"This file looks like **{detected}** data, but **Dataset** is set to **{expected}**. "
            f"Switch to **{other}** in the sidebar, or upload an **{expected}** file."
        )
    return None
