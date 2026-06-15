"""Dry-run validation and merge stats for sidebar upload preview."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from config.settings import COL_BRAND_NAME, COL_SUPPLIER, COL_TYPE
from services.upload_dataset_validation import validate_upload_dataset_match
from services.upload_ingest_service import classify_upload_format
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
    dataset_mismatch: bool = False
    sample: pd.DataFrame | None = None
    processed_csv: bytes | None = None
    processed_download_name: str = ""

def build_processed_download_payload(df: pd.DataFrame, original_file_name: str) -> tuple[bytes, str]:
    """CSV bytes + filename for ETL-processed upload (utf-8-sig, same schema as merge)."""
    stem = Path(original_file_name).stem or "upload"
    filename = f"processed_{stem}.csv"
    csv_text = df.to_csv(index=False, encoding="utf-8-sig")
    return csv_text.encode("utf-8-sig"), filename


def classify_upload_headers(df: pd.DataFrame) -> str:
    return classify_upload_format(df)


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
        "quarter",
        "type_sale",
        "Sale_chanel",
        "saler",
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

        mismatch_msg = validate_upload_dataset_match(
            header_preview,
            dataset_mode=dataset_mode,
            file_name=file_name,
        )
        if mismatch_msg:
            result.dataset_mismatch = True
            result.error = mismatch_msg
            result.ml_ready = False
            result.ready_for_merge = False
            return result

        incoming_df = ingest_file_fn(temp_path, hs_codes=hs_codes)
        result.row_count = len(incoming_df)
        if not incoming_df.empty:
            result.processed_csv, result.processed_download_name = build_processed_download_payload(
                incoming_df, file_name
            )
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
