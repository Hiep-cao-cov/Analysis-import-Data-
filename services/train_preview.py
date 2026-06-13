"""Dataset summary and preview before model training."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from config.settings import COL_BRAND_NAME, COL_SUPPLIER, COL_TYPE, DEFAULT_RARE_CLASS_LABEL
from services.k_fold_muilti_task import ColumnConfig, fix_scientific_notation
from services.data_loader_service import infer_hs_codes_for_path, load_for_ml
from services.train_service import build_column_config
from services.training_config import RARE_BRAND_MODE_DROP, RARE_BRAND_MODE_MERGE, TrainConfig


@dataclass
class BrandProcessingStats:
    rare_brands: list[tuple[str, int]] = field(default_factory=list)
    excluded_brands: list[tuple[str, int]] = field(default_factory=list)
    singleton_brands: list[tuple[str, int]] = field(default_factory=list)
    rows_removed: int = 0


@dataclass
class DatasetTrainSummary:
    file_name: str
    product_guess: str
    rows: int
    n_brand_before: int
    n_brand_after: int
    n_type: int
    n_supplier: int
    n_rows_dropped_na: int
    n_rows_excluded_brands: int = 0
    min_class_count: int = 0
    max_class_count: int = 0
    recommended_n_folds: int = 2
    recommended_n_folds_if_singletons_removed: int = 2
    rare_brands: list[tuple[str, int]] = field(default_factory=list)
    excluded_brands: list[tuple[str, int]] = field(default_factory=list)
    singleton_brands: list[tuple[str, int]] = field(default_factory=list)
    all_brand_counts: list[tuple[str, int]] = field(default_factory=list)
    top_brands: pd.DataFrame = field(default_factory=pd.DataFrame)
    type_counts: pd.DataFrame = field(default_factory=pd.DataFrame)
    supplier_counts: pd.DataFrame = field(default_factory=pd.DataFrame)
    error: str | None = None


def _clean_training_columns(df: pd.DataFrame, col: ColumnConfig) -> tuple[pd.DataFrame, int]:
    out = df.copy()
    before = len(out)
    out[col.product_description] = out[col.product_description].apply(fix_scientific_notation)
    out[col.hs_code] = out[col.hs_code].astype(str).str.zfill(8)
    out[col.saler] = out[col.saler].fillna("UNKNOWN")
    out[col.country_origin] = out[col.country_origin].fillna("UNKNOWN")
    out[col.label] = out[col.label].astype(str).str.strip()
    if col.type_col:
        out[col.type_col] = out[col.type_col].astype(str).str.strip()
    if col.supplier_col:
        out[col.supplier_col] = out[col.supplier_col].astype(str).str.strip()
    out.dropna(subset=[col.hs_code, col.product_description, col.label], inplace=True)
    return out, before - len(out)


def apply_rare_brand_merge(
    df: pd.DataFrame,
    label_col: str,
    *,
    min_samples: int,
    rare_label: str,
) -> tuple[pd.DataFrame, list[tuple[str, int]]]:
    out = df.copy()
    counts = out[label_col].value_counts()
    rare = [(str(name), int(counts[name])) for name in counts.index if counts[name] < min_samples]
    rare_names = {name for name, _ in rare}
    if rare_names:
        out[label_col] = out[label_col].apply(lambda x: rare_label if x in rare_names else x)
    return out, rare


def _brand_count_list(series: pd.Series) -> list[tuple[str, int]]:
    counts = series.value_counts()
    return [(str(name), int(counts[name])) for name in counts.index]


def apply_brand_training_rules(
    df: pd.DataFrame,
    label_col: str,
    config: TrainConfig,
) -> tuple[pd.DataFrame, BrandProcessingStats]:
    """
    Apply rare-brand merge OR drop, manual exclusions, and optional singleton removal.
    """
    out = df.copy()
    stats = BrandProcessingStats()
    counts = out[label_col].value_counts()
    rare_label = (config.rare_class_label or DEFAULT_RARE_CLASS_LABEL).strip()
    min_samples = max(1, int(config.min_samples_per_class))

    if config.rare_brand_mode == RARE_BRAND_MODE_DROP:
        drop_names = {str(n) for n in counts.index if counts[n] < min_samples}
        stats.rare_brands = [(n, int(counts[n])) for n in drop_names if n in counts.index]
        if drop_names:
            before = len(out)
            out = out[~out[label_col].isin(drop_names)].copy()
            stats.rows_removed += before - len(out)
    else:
        out, stats.rare_brands = apply_rare_brand_merge(
            out, label_col, min_samples=min_samples, rare_label=rare_label
        )

    manual = {str(b).strip() for b in config.exclude_brands if str(b).strip()}
    if manual:
        counts = out[label_col].value_counts()
        present = manual & set(counts.index.astype(str))
        if present:
            before = len(out)
            out = out[~out[label_col].astype(str).isin(present)].copy()
            stats.rows_removed += before - len(out)
            stats.excluded_brands = [(b, int(counts[b])) for b in present if b in counts.index]

    if config.auto_exclude_singletons and len(out):
        counts = out[label_col].value_counts()
        singletons = {str(n) for n in counts.index if counts[n] == 1}
        if singletons:
            before = len(out)
            out = out[~out[label_col].astype(str).isin(singletons)].copy()
            stats.rows_removed += before - len(out)
            stats.singleton_brands = [(b, 1) for b in singletons]

    return out.reset_index(drop=True), stats


def effective_n_folds(requested: int, min_class_count: int) -> int:
    if min_class_count < 2:
        return 2
    return max(2, min(requested, int(min_class_count)))


def _build_summary_from_frame(
    df: pd.DataFrame,
    col: ColumnConfig,
    *,
    path: Path,
    guess: str,
    brand_before: int,
    dropped_na: int,
    requested_n_folds: int,
    processing: BrandProcessingStats,
) -> DatasetTrainSummary:
    counts_after = df[col.label].value_counts()
    min_after = int(counts_after.min()) if len(counts_after) else 0
    all_brands = _brand_count_list(df[col.label])
    singletons = [(n, c) for n, c in all_brands if c == 1]

    # Folds if we removed singletons (what-if for UI hint)
    drop_single_names = {n for n, c in singletons}
    if drop_single_names:
        df_no_single = df[~df[col.label].isin(drop_single_names)].copy()
        c2 = df_no_single[col.label].value_counts()
        min_if = int(c2.min()) if len(c2) else 0
    else:
        min_if = min_after

    top_brands = (
        counts_after.head(15).rename("rows").reset_index().rename(columns={col.label: "BRAND NAME"})
    )

    return DatasetTrainSummary(
        file_name=path.name,
        product_guess=guess,
        rows=len(df),
        n_brand_before=brand_before,
        n_brand_after=int(df[col.label].nunique()),
        n_type=int(df[col.type_col].nunique()) if col.type_col in df.columns else 0,
        n_supplier=int(df[col.supplier_col].nunique()) if col.supplier_col in df.columns else 0,
        n_rows_dropped_na=dropped_na,
        n_rows_excluded_brands=processing.rows_removed,
        min_class_count=min_after,
        max_class_count=int(counts_after.max()) if len(counts_after) else 0,
        recommended_n_folds=effective_n_folds(requested_n_folds, min_after),
        recommended_n_folds_if_singletons_removed=effective_n_folds(requested_n_folds, min_if),
        rare_brands=processing.rare_brands,
        excluded_brands=processing.excluded_brands,
        singleton_brands=singletons,
        all_brand_counts=all_brands,
        top_brands=top_brands,
        type_counts=(
            df[COL_TYPE].value_counts().head(10).rename("rows").reset_index()
            if COL_TYPE in df.columns
            else pd.DataFrame()
        ),
        supplier_counts=(
            df[COL_SUPPLIER].value_counts().head(10).rename("rows").reset_index()
            if COL_SUPPLIER in df.columns
            else pd.DataFrame()
        ),
    )


def analyze_training_dataset(
    dataset_path: Path | str,
    config: TrainConfig | None = None,
) -> DatasetTrainSummary:
    config = config or TrainConfig()
    path = Path(dataset_path)
    col = build_column_config()
    guess = "TDI" if "tdi" in path.name.lower() else ("PMDI" if "pmdi" in path.name.lower() or "mdi" in path.name.lower() else "Auto")

    try:
        df = load_for_ml(path)
        col.validate(df, require_targets=True)
    except Exception as e:
        return DatasetTrainSummary(
            file_name=path.name,
            product_guess=guess,
            rows=0,
            n_brand_before=0,
            n_brand_after=0,
            n_type=0,
            n_supplier=0,
            n_rows_dropped_na=0,
            error=str(e),
        )

    df, dropped = _clean_training_columns(df, col)
    brand_before = int(df[col.label].nunique())

    df_final, processing = apply_brand_training_rules(df, col.label, config)

    if len(df_final) == 0:
        return DatasetTrainSummary(
            file_name=path.name,
            product_guess=guess,
            rows=0,
            n_brand_before=brand_before,
            n_brand_after=0,
            error="No rows left after brand exclusions. Lower min samples or uncheck exclusions.",
        )

    hs_codes = infer_hs_codes_for_path(path)
    if hs_codes and "hs_code" in df.columns:
        guess = "TDI" if "292910" in "".join(hs_codes[:1]) else "PMDI"

    return _build_summary_from_frame(
        df_final,
        col,
        path=path,
        guess=guess,
        brand_before=brand_before,
        dropped_na=dropped,
        requested_n_folds=config.n_folds,
        processing=processing,
    )


def suggested_auto_excludes(summary: DatasetTrainSummary, config: TrainConfig) -> list[str]:
    """Brands to pre-select for exclusion: singletons when auto flag is on."""
    if not config.auto_exclude_singletons:
        return list(config.exclude_brands)
    names = {n for n, _ in summary.singleton_brands}
    names.update(str(b) for b in config.exclude_brands)
    return sorted(names)
