"""Dry-run validation and merge stats for sidebar upload preview."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from config.settings import COL_BRAND_NAME, COL_SUPPLIER, COL_TYPE
from services.data_loader_service import (
    is_prediction_export,
    is_raw_customs_export,
    is_standardized_dataset,
    resolve_ingest_force_etl,
)
from services.data_paths import resolve_analysis_dataset
from services.ml_columns import has_ml_target_columns, missing_ml_target_names


@dataclass
class UploadPreviewResult:
    """Outcome of parsing an upload and comparing it to the saved dataset."""

    file_name: str
    file_kind: str
    row_count: int = 0
    ml_ready: bool = False
    ready_for_merge: bool = False
    missing_ml_columns: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error: str | None = None
    upload_coverage: str | None = None
    base_coverage: str | None = None
    base_row_count: int = 0
    new_rows: int = 0
    duplicate_rows: int = 0
    total_after_merge: int = 0
    already_merged: bool = False
    sample: pd.DataFrame | None = None

    def as_dict(self) -> dict:
        return {
            "file_name": self.file_name,
            "file_kind": self.file_kind,
            "row_count": self.row_count,
            "ml_ready": self.ml_ready,
            "ready_for_merge": self.ready_for_merge,
            "missing_ml_columns": list(self.missing_ml_columns),
            "warnings": list(self.warnings),
            "error": self.error,
            "upload_coverage": self.upload_coverage,
            "base_coverage": self.base_coverage,
            "base_row_count": self.base_row_count,
            "new_rows": self.new_rows,
            "duplicate_rows": self.duplicate_rows,
            "total_after_merge": self.total_after_merge,
            "already_merged": self.already_merged,
            "sample": self.sample,
        }


def classify_upload_headers(df: pd.DataFrame) -> str:
    if is_prediction_export(df):
        return "Prediction export"
    if is_standardized_dataset(df):
        return "Standardized dataset"
    if is_raw_customs_export(df):
        return "Raw customs (ETL on merge)"
    return "Unrecognized format"


def format_date_coverage(df: pd.DataFrame | None) -> str | None:
    if df is None or df.empty:
        return None

    if "date" in df.columns:
        dates = pd.to_datetime(df["date"], errors="coerce").dropna()
        if not dates.empty:
            start = dates.min().strftime("%b %Y")
            end = dates.max().strftime("%b %Y")
            return start if start == end else f"{start} → {end}"

    if "year" in df.columns:
        years = pd.to_numeric(df["year"], errors="coerce").dropna()
        if years.empty:
            return None
        y_min, y_max = int(years.min()), int(years.max())
        if "month" in df.columns:
            month_map = {
                "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
                "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
            }
            periods: list[tuple[int, int]] = []
            for _, row in df[["year", "month"]].dropna(how="all").iterrows():
                try:
                    y = int(float(row["year"]))
                except (TypeError, ValueError):
                    continue
                m_raw = str(row.get("month", "")).strip().lower()[:3]
                m = month_map.get(m_raw)
                if m:
                    periods.append((y, m))
            if periods:
                periods.sort()
                y1, m1 = periods[0]
                y2, m2 = periods[-1]
                start = pd.Timestamp(year=y1, month=m1, day=1).strftime("%b %Y")
                end = pd.Timestamp(year=y2, month=m2, day=1).strftime("%b %Y")
                return start if start == end else f"{start} → {end}"
        return str(y_min) if y_min == y_max else f"{y_min} → {y_max}"

    return None


def _optional_column_warnings(df: pd.DataFrame) -> list[str]:
    warnings: list[str] = []
    if "volume" not in df.columns:
        warnings.append("No **volume** column — volume charts may be empty.")
    if "date" not in df.columns and "year" not in df.columns:
        warnings.append("No **date** or **year** — year filters may not work.")
    if "month" not in df.columns and "date" not in df.columns:
        warnings.append("No **month** or **date** — monthly charts may be limited.")
    if "total_usd" not in df.columns:
        warnings.append("No **total_usd** — USD value KPIs may be unavailable.")
    return warnings


def _sample_preview_df(df: pd.DataFrame, limit: int = 5) -> pd.DataFrame:
    preferred = [
        "date",
        "year",
        "month",
        "customer_name",
        "hs_code",
        "volume",
        COL_BRAND_NAME,
        COL_SUPPLIER,
        COL_TYPE,
    ]
    cols = [c for c in preferred if c in df.columns]
    if not cols:
        cols = list(df.columns[:8])
    return df[cols].head(limit).copy()


def build_upload_preview(
    *,
    file_name: str,
    file_bytes: bytes,
    temp_path: Path,
    dataset_mode: str,
    hs_codes: list[str] | None,
    last_merge_token: str | None,
    ingest_file_fn,
    load_default_data_fn,
    append_only_new_rows_fn,
    prepare_dataset_for_storage_fn,
) -> UploadPreviewResult:
    """
    Parse upload, validate ML columns, and dry-run merge against saved dataset.
    Dependencies injected to avoid circular imports with ui.analysis_data.
    """
    upload_token = f"{file_name}:{len(file_bytes)}"
    result = UploadPreviewResult(file_name=file_name, file_kind="—")

    if last_merge_token and last_merge_token == upload_token:
        result.already_merged = True
        result.file_kind = "Already merged"
        result.ready_for_merge = False

    temp_path.write_bytes(file_bytes)

    try:
        if temp_path.suffix.lower() == ".csv":
            header_preview = pd.read_csv(temp_path, nrows=20, low_memory=False)
        else:
            header_preview = pd.read_excel(temp_path, nrows=20)
        header_preview.columns = [str(c).strip() for c in header_preview.columns]
        result.file_kind = classify_upload_headers(header_preview)
        force_etl = resolve_ingest_force_etl(header_preview)

        incoming_df = ingest_file_fn(temp_path, force_etl=force_etl, hs_codes=hs_codes)
        incoming_df = prepare_dataset_for_storage_fn(incoming_df)
        result.row_count = len(incoming_df)
        result.upload_coverage = format_date_coverage(incoming_df)
        result.sample = _sample_preview_df(incoming_df)

        result.missing_ml_columns = missing_ml_target_names(incoming_df)
        result.ml_ready = has_ml_target_columns(incoming_df)
        result.warnings = _optional_column_warnings(incoming_df)

        load_path = resolve_analysis_dataset(dataset_mode)
        base_df = load_default_data_fn(load_path, hs_codes=hs_codes)
        if base_df is not None and not base_df.empty:
            result.base_row_count = len(base_df)
            result.base_coverage = format_date_coverage(base_df)
        else:
            base_df = pd.DataFrame()

        if result.ml_ready and not base_df.empty:
            _, new_rows, dup_rows = append_only_new_rows_fn(base_df, incoming_df)
            result.new_rows = new_rows
            result.duplicate_rows = dup_rows
            result.total_after_merge = len(base_df) + new_rows
        elif result.ml_ready:
            result.new_rows = len(incoming_df)
            result.duplicate_rows = 0
            result.total_after_merge = len(incoming_df)

        result.ready_for_merge = (
            result.ml_ready
            and not result.already_merged
            and result.error is None
        )
    except Exception as exc:
        result.error = str(exc)
        result.ready_for_merge = False

    return result
