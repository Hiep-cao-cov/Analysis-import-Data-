"""Prediction service: standardized dataset + model → predictions."""
from pathlib import Path

import pandas as pd

from services.data_loader_service import load_file
from services.k_fold_muilti_task import MaterialPredictionPipeline
from services.ml_compat import register_legacy_ml_module_aliases
from services.predict_prepare import PredictFilterStats, ProgressCallback, _report_progress, prepare_and_predict

register_legacy_ml_module_aliases()


def load_model(model_dir: str | Path) -> MaterialPredictionPipeline:
    return MaterialPredictionPipeline.load(str(model_dir))


def run_predict(
    df: pd.DataFrame,
    model_dir: str | Path,
    *,
    source_path: str | Path | None = None,
    product_line: str | None = None,
    progress_callback: ProgressCallback | None = None,
) -> tuple[pd.DataFrame, PredictFilterStats]:
    """
    Run prediction on eligible rows; output keeps every input row with mark columns.

    Returns (predictions_df, filter_stats).
    """
    line_label = product_line or "model"
    _report_progress(progress_callback, 0.02, f"Loading {line_label} prediction model…")
    pipeline = load_model(model_dir)
    result = prepare_and_predict(
        df,
        pipeline,
        source_path=source_path,
        product_line=product_line,
        progress_callback=progress_callback,
    )
    _report_progress(progress_callback, 1.0, "Prediction complete")
    return result


def run_predict_from_file(
    dataset_path: str | Path,
    model_dir: str | Path,
    *,
    product_line: str | None = None,
) -> tuple[pd.DataFrame, PredictFilterStats]:
    path = Path(dataset_path)
    df = load_file(path)
    pipeline = load_model(model_dir)
    return prepare_and_predict(
        df,
        pipeline,
        source_path=path,
        product_line=product_line,
    )
