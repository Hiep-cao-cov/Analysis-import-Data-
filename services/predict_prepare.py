"""Row marking for Predict new — keep all input rows, annotate delete reasons."""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias

import numpy as np
import pandas as pd

from config.settings import (
    ALLOWED_UNITS,
    COL_BRAND_NAME,
    COL_SUPPLIER,
    COL_TYPE,
    MDI_HS_CODES,
    ML_COLUMN_CONFIG,
    PREDICT_CONFIDENCE_COLUMNS,
    TDI_HS_CODES,
)
from services.brand_labels import should_mark_unknown_brand_row, unknown_brand_delete_reason
from services.customer_name_service import apply_customer_short_names
from services.data_loader_service import (
    has_ml_feature_columns,
    is_raw_customs_export,
    load_for_ml,
)
from services.description_blacklist import (
    blacklist_delete_reason,
    find_description_blacklist_match,
    get_description_blacklist_terms,
    normalize_description_text,
)
from services.ml_columns import (
    EXPORT_PRESERVE_PREFIX,
    _STORAGE_DERIVED_COLUMNS,
    apply_predictions_to_targets,
    finalize_export_unit_columns,
    normalize_ml_column_names,
)

MARK_FOR_DELETE_COL = "marked_for_delete"
DELETE_REASON_COL = "delete_reason"

ProgressCallback: TypeAlias = Callable[[float, str], None]


def _report_progress(callback: ProgressCallback | None, pct: float, message: str) -> None:
    if callback is not None:
        callback(min(1.0, max(0.0, pct)), message)

PREDICT_OVERLAY_COLUMNS = (COL_BRAND_NAME, COL_SUPPLIER, COL_TYPE)
PREDICT_OVERLAY_CONFIDENCE_COLUMNS = PREDICT_CONFIDENCE_COLUMNS
PREDICT_EXPORT_NEW_COLUMNS = frozenset(
    {
        COL_BRAND_NAME,
        COL_SUPPLIER,
        COL_TYPE,
        *PREDICT_CONFIDENCE_COLUMNS,
        MARK_FOR_DELETE_COL,
        DELETE_REASON_COL,
    }
)

def normalize_filter_text(text) -> str:
    return normalize_description_text(text)


def normalize_hs_code(value) -> str:
    return str(value).replace(".", "").strip()


def resolve_hs_codes_for_product_line(product_line: str | None) -> list[str] | None:
    pl = (product_line or "").strip().upper()
    if pl in ("PMDI", "MDI"):
        return MDI_HS_CODES
    if pl == "TDI":
        return TDI_HS_CODES
    return None


def _resolve_rule_columns(df: pd.DataFrame) -> dict[str, str | None]:
    lower_to_actual = {str(c).strip().lower(): c for c in df.columns}

    def pick(*names: str) -> str | None:
        for name in names:
            if name in lower_to_actual:
                return lower_to_actual[name]
        return None

    return {
        "description": pick("description", "chung loai hang hoa xuat nhap"),
        "unit": pick("unit", "dvt"),
        "hs_code": pick("hs_code", "hs code"),
        "total_usd": pick("total_usd", "tri gia usd"),
        "saler": pick("saler", "don vi doi tac"),
        "country_origin": pick("country_origin", "nuoc xuat xu"),
    }


def assign_predict_row_id(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy().reset_index(drop=True)
    out["_predict_row_id"] = np.arange(len(out), dtype=np.int64)
    return out


def build_pre_predict_reasons(
    df: pd.DataFrame,
    *,
    product_line: str | None,
    hs_codes: list[str] | None,
) -> pd.Series:
    """Per-row reasons before prediction. Empty string = eligible for model."""
    cols = _resolve_rule_columns(df)
    terms = get_description_blacklist_terms(product_line=product_line)
    allowed_units = {normalize_filter_text(u) for u in ALLOWED_UNITS}
    clean_hs_targets = {normalize_hs_code(c) for c in (hs_codes or [])}
    pl_label = (product_line or "model").strip().upper()

    reasons: list[str] = []
    for _, row in df.iterrows():
        row_reasons: list[str] = []

        desc_col = cols["description"]
        if desc_col and terms:
            match = find_description_blacklist_match(
                row.get(desc_col, ""),
                terms,
                product_line=product_line,
            )
            if match:
                row_reasons.append(blacklist_delete_reason(match, product_line=product_line))

        hs_col = cols["hs_code"]
        if clean_hs_targets and hs_col:
            raw_hs = row.get(hs_col, "")
            hs_val = normalize_hs_code(raw_hs)
            if not hs_val or hs_val not in clean_hs_targets:
                row_reasons.append(
                    f"hs_code_filter: HS code '{raw_hs}' is not in allowed {pl_label} list "
                    f"({', '.join(sorted(clean_hs_targets))})"
                )

        unit_col = cols["unit"]
        if unit_col:
            unit_val = normalize_filter_text(row.get(unit_col, ""))
            if unit_val and unit_val not in allowed_units:
                row_reasons.append(
                    f"unit_filter: unit '{row.get(unit_col, '')}' is not allowed "
                    f"(allowed: {', '.join(sorted(allowed_units))}; only kg rows are kept after ETL)"
                )

        total_col = cols["total_usd"]
        if total_col and pd.isna(row.get(total_col)):
            row_reasons.append("missing_total_usd: total_usd / tri gia usd is missing")

        if not row_reasons:
            missing_features: list[str] = []
            feat_to_col = {
                ML_COLUMN_CONFIG["hs_code"]: cols["hs_code"],
                ML_COLUMN_CONFIG["product_description"]: cols["description"],
                ML_COLUMN_CONFIG["saler"]: cols["saler"],
                ML_COLUMN_CONFIG["country_origin"]: cols["country_origin"],
            }
            for feat_name, actual in feat_to_col.items():
                if actual is None:
                    missing_features.append(feat_name)
                    continue
                val = row.get(actual, "")
                if pd.isna(val) or str(val).strip().lower() in ("", "nan", "none"):
                    missing_features.append(feat_name)
            if missing_features:
                row_reasons.append(
                    "missing_features: required prediction columns empty or missing — "
                    + ", ".join(missing_features)
                )

        reasons.append("; ".join(row_reasons))

    return pd.Series(reasons, index=df.index, dtype="object")


def build_ml_prediction_frame(
    input_df: pd.DataFrame,
    pre_reasons: pd.Series,
    *,
    source_path: str | Path | None,
    product_line: str | None,
    hs_codes: list[str] | None,
) -> pd.DataFrame:
    eligible_mask = pre_reasons.astype(str).str.strip() == ""
    if not eligible_mask.any():
        return pd.DataFrame()

    eligible_ids = set(input_df.loc[eligible_mask, "_predict_row_id"].tolist())
    path = Path(source_path) if source_path else None
    use_full_etl = path is not None and path.is_file() and (
        is_raw_customs_export(input_df) or not has_ml_feature_columns(input_df)
    )

    if use_full_etl:
        ml_df = load_for_ml(path, hs_codes=hs_codes)
        if "_predict_row_id" not in ml_df.columns:
            raise ValueError(
                "ETL output is missing _predict_row_id — cannot align predictions to input rows. "
                "Re-upload the file and try again."
            )
        return ml_df[ml_df["_predict_row_id"].isin(eligible_ids)].copy().reset_index(drop=True)

    ml_df = apply_customer_short_names(
        normalize_ml_column_names(input_df.loc[eligible_mask].copy())
    )
    return ml_df.reset_index(drop=True)


def apply_post_predict_markers(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if COL_BRAND_NAME not in out.columns:
        return out

    type_series = out[COL_TYPE] if COL_TYPE in out.columns else pd.Series([None] * len(out), index=out.index)
    mark_mask = pd.Series(
        [
            should_mark_unknown_brand_row(brand, type_val)
            for brand, type_val in zip(out[COL_BRAND_NAME], type_series, strict=False)
        ],
        index=out.index,
    )
    post_msg = unknown_brand_delete_reason()
    for idx in out.index[mark_mask]:
        existing = str(out.at[idx, DELETE_REASON_COL]).strip()
        out.at[idx, DELETE_REASON_COL] = f"{existing}; {post_msg}" if existing else post_msg
    return out


def prepare_predict_export(df: pd.DataFrame) -> pd.DataFrame:
    """Drop internal columns only — never drop marked rows."""
    out = df.copy()
    drop: list[str] = []
    for col in out.columns:
        c = str(col)
        if c.startswith(EXPORT_PRESERVE_PREFIX) or c == "_predict_row_id":
            drop.append(c)
    for col in _STORAGE_DERIVED_COLUMNS:
        if col in out.columns:
            drop.append(col)
    out = out.drop(columns=list(dict.fromkeys(drop)), errors="ignore")
    return finalize_export_unit_columns(out)


def finalize_predict_column_layout(
    df: pd.DataFrame,
    original_columns: list[str],
) -> pd.DataFrame:
    """Keep upload column names/order; append prediction + mark columns only."""
    ordered: list[str] = [col for col in original_columns if col in df.columns]
    for col in (
        *PREDICT_OVERLAY_COLUMNS,
        *PREDICT_OVERLAY_CONFIDENCE_COLUMNS,
        MARK_FOR_DELETE_COL,
        DELETE_REASON_COL,
    ):
        if col in df.columns and col not in ordered:
            ordered.append(col)
    return df[ordered].copy()


def assemble_full_predict_output(
    input_df: pd.DataFrame,
    predicted_df: pd.DataFrame,
    pre_reasons: pd.Series,
    *,
    original_columns: list[str],
) -> pd.DataFrame:
    out = input_df.copy()

    if not predicted_df.empty and "_predict_row_id" in predicted_df.columns:
        pred = apply_predictions_to_targets(predicted_df.copy()).set_index("_predict_row_id")
        for rid, row in pred.iterrows():
            mask = out["_predict_row_id"] == rid
            if not mask.any():
                continue
            for col in (*PREDICT_OVERLAY_COLUMNS, *PREDICT_OVERLAY_CONFIDENCE_COLUMNS):
                if col in row.index:
                    out.loc[mask, col] = row[col]

    out[DELETE_REASON_COL] = pre_reasons.astype(str).values
    out = apply_post_predict_markers(out)
    out[MARK_FOR_DELETE_COL] = out[DELETE_REASON_COL].astype(str).str.strip().map(
        lambda text: "Yes" if text else "No"
    )
    out = finalize_predict_column_layout(out, original_columns)
    return prepare_predict_export(out)


def filter_predict_download(df: pd.DataFrame, *, exclude_marked: bool) -> pd.DataFrame:
    if not exclude_marked or MARK_FOR_DELETE_COL not in df.columns:
        return df.copy()
    return df[df[MARK_FOR_DELETE_COL].astype(str).str.strip().str.lower() != "yes"].copy()


def filter_predict_download_options(
    df: pd.DataFrame,
    *,
    exclude_marked: bool,
    include_confidence: bool,
) -> pd.DataFrame:
    out = filter_predict_download(df, exclude_marked=exclude_marked)
    if not include_confidence:
        out = out.drop(columns=[c for c in PREDICT_CONFIDENCE_COLUMNS if c in out.columns], errors="ignore")
    return out


def count_reason_tags(series: pd.Series, tag: str) -> int:
    return int(series.astype(str).str.contains(tag, regex=False, na=False).sum())


@dataclass
class PredictFilterStats:
    rows_input: int = 0
    used_full_etl: bool = False
    rows_predicted: int = 0
    rows_output: int = 0
    marked_for_delete: int = 0
    marked_delete_description: int = 0
    marked_hs_code: int = 0
    marked_unit: int = 0
    marked_missing_total_usd: int = 0
    marked_missing_features: int = 0
    marked_unknown_brand: int = 0

    @classmethod
    def from_output(cls, input_rows: int, predicted_rows: int, output_df: pd.DataFrame, *, used_full_etl: bool) -> PredictFilterStats:
        reasons = output_df.get(DELETE_REASON_COL, pd.Series(dtype=str))
        marked = output_df.get(MARK_FOR_DELETE_COL, pd.Series(dtype=str))
        stats = cls(
            rows_input=input_rows,
            used_full_etl=used_full_etl,
            rows_predicted=predicted_rows,
            rows_output=len(output_df),
            marked_for_delete=int((marked.astype(str).str.strip().str.lower() == "yes").sum()),
            marked_delete_description=count_reason_tags(reasons, "delete_description:"),
            marked_hs_code=count_reason_tags(reasons, "hs_code_filter:"),
            marked_unit=count_reason_tags(reasons, "unit_filter:"),
            marked_missing_total_usd=count_reason_tags(reasons, "missing_total_usd:"),
            marked_missing_features=count_reason_tags(reasons, "missing_features:"),
            marked_unknown_brand=(
                count_reason_tags(reasons, "unknown_brand:")
                + count_reason_tags(reasons, "other_chemical:")
            ),
        )
        return stats

    def summary_lines(self) -> list[str]:
        lines = [
            f"Input rows: **{self.rows_input:,}**",
            f"Output rows: **{self.rows_output:,}** (same count as input)",
            f"Rows sent to model: **{self.rows_predicted:,}**",
            f"Rows marked for deletion: **{self.marked_for_delete:,}**",
        ]
        if self.used_full_etl:
            lines.append("Preparation: full ETL for raw / non-standard files")
        rule_parts: list[str] = []
        if self.marked_delete_description:
            rule_parts.append(f"delete_description {self.marked_delete_description:,}")
        if self.marked_hs_code:
            rule_parts.append(f"hs_code_filter {self.marked_hs_code:,}")
        if self.marked_unit:
            rule_parts.append(f"unit_filter {self.marked_unit:,}")
        if self.marked_missing_total_usd:
            rule_parts.append(f"missing_total_usd {self.marked_missing_total_usd:,}")
        if self.marked_missing_features:
            rule_parts.append(f"missing_features {self.marked_missing_features:,}")
        if self.marked_unknown_brand:
            rule_parts.append(f"unknown_brand {self.marked_unknown_brand:,}")
        if rule_parts:
            lines.append("Marked by rule: " + ", ".join(rule_parts))
        return lines


def prepare_and_predict(
    input_df: pd.DataFrame,
    pipeline,
    *,
    source_path: str | Path | None,
    product_line: str | None,
    progress_callback: ProgressCallback | None = None,
) -> tuple[pd.DataFrame, PredictFilterStats]:
    """Mark rows, predict eligible subset, merge back to full input row count."""
    line_label = product_line or "model"
    _report_progress(progress_callback, 0.08, f"Reading {len(input_df):,} input rows…")

    original_columns = [col for col in input_df.columns if str(col) != "_predict_row_id"]
    full_input = assign_predict_row_id(input_df)
    hs_codes = resolve_hs_codes_for_product_line(product_line)
    path = Path(source_path) if source_path else None
    used_full_etl = path is not None and path.is_file() and (
        is_raw_customs_export(full_input) or not has_ml_feature_columns(full_input)
    )

    _report_progress(
        progress_callback,
        0.18,
        "Checking validation rules (description blacklist, HS code, unit, total USD)…",
    )
    pre_reasons = build_pre_predict_reasons(
        full_input,
        product_line=product_line,
        hs_codes=hs_codes,
    )

    prep_msg = (
        "Standardizing raw customs data (ETL)…"
        if used_full_etl
        else "Preparing feature columns for the model…"
    )
    _report_progress(progress_callback, 0.32, prep_msg)
    ml_df = build_ml_prediction_frame(
        full_input,
        pre_reasons,
        source_path=source_path,
        product_line=product_line,
        hs_codes=hs_codes,
    )

    eligible_ids = set(full_input.loc[pre_reasons.astype(str).str.strip() == "", "_predict_row_id"])
    if not ml_df.empty and "_predict_row_id" in ml_df.columns:
        etl_gap = eligible_ids - set(ml_df["_predict_row_id"].tolist())
    else:
        etl_gap = eligible_ids
    if etl_gap:
        gap_msg = (
            "etl_excluded: row dropped during ETL preparation "
            "(description blacklist, HS code, unit, or missing total_usd)"
        )
        for idx in full_input.index[full_input["_predict_row_id"].isin(etl_gap)]:
            pre_reasons.at[idx] = gap_msg

    predicted = pd.DataFrame()
    if not ml_df.empty:
        _report_progress(
            progress_callback,
            0.55,
            f"Running {line_label} model inference on {len(ml_df):,} eligible rows…",
        )
        predicted = pipeline.predict(ml_df)
    else:
        _report_progress(
            progress_callback,
            0.55,
            "No eligible rows for model — building marked output only…",
        )

    _report_progress(
        progress_callback,
        0.82,
        "Merging BRAND NAME, SUPPLIER, and TYPE into output…",
    )
    out = assemble_full_predict_output(
        full_input,
        predicted,
        pre_reasons,
        original_columns=original_columns,
    )
    _report_progress(progress_callback, 0.95, "Finalizing export columns…")
    stats = PredictFilterStats.from_output(
        input_rows=len(full_input),
        predicted_rows=len(ml_df),
        output_df=out,
        used_full_etl=used_full_etl,
    )
    return out, stats
