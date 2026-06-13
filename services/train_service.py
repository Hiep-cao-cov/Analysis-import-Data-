"""Training service: labeled dataset → saved multi-task model."""

from __future__ import annotations



from pathlib import Path

from typing import Callable



from config.settings import DEFAULT_RANDOM_STATE, ML_COLUMN_CONFIG

from services.k_fold_muilti_task import ColumnConfig, MaterialPredictionPipeline

from services.training_config import TrainConfig



TrainProgressCallback = Callable[[float, str], None]





def build_column_config() -> ColumnConfig:

    c = ML_COLUMN_CONFIG

    return ColumnConfig(

        hs_code=c["hs_code"],

        product_description=c["product_description"],

        saler=c["saler"],

        country_origin=c["country_origin"],

        label=c["label"],

        type_col=c["type_col"],

        supplier_col=c["supplier_col"],

    )





def run_train(

    dataset_path: str | Path,

    model_dir: str | Path,

    *,

    config: TrainConfig | None = None,

    progress_callback: TrainProgressCallback | None = None,

) -> dict:

    """

    Train multi-task model and save artifacts. Returns summary metrics dict.

    """

    config = config or TrainConfig()

    model_dir = Path(model_dir)

    model_dir.mkdir(parents=True, exist_ok=True)



    col_config = build_column_config()

    pipeline = MaterialPredictionPipeline(

        column_config=col_config,

        use_multitask=True,

        random_state=config.random_state,

        n_folds=config.n_folds,

        word_tfidf_max=config.word_tfidf_max,

        char_tfidf_max=config.char_tfidf_max,

        min_samples_per_class=config.min_samples_per_class,

        rare_class_label=config.rare_class_label,
        rare_brand_mode=config.rare_brand_mode,
        exclude_brands=config.exclude_brands,
        auto_exclude_singletons=config.auto_exclude_singletons,
        multitask_aux_weight=config.multitask_aux_weight,
    )



    def report(fraction: float, message: str) -> None:

        if progress_callback is not None:

            progress_callback(fraction, message)



    report(0.02, "Loading dataset and running ETL if needed…")

    df = pipeline.load_and_prepare(str(dataset_path))

    report(

        0.12,

        f"Data ready · {len(df):,} rows · {df[col_config.label].nunique()} brand classes",

    )

    pipeline.train(

        df,

        epochs=config.epochs,

        batch_size=config.batch_size,

        progress_callback=progress_callback,

    )

    report(0.98, "Saving model and encoders to disk…")

    pipeline.save(str(model_dir))

    report(1.0, "Training complete.")



    return {

        "rows": len(df),

        "classes": int(df[col_config.label].nunique()),

        "mean_cv_accuracy": float(sum(pipeline.cv_accuracies) / len(pipeline.cv_accuracies))

        if pipeline.cv_accuracies

        else None,

        "mean_cv_top3": float(sum(pipeline.cv_top3_accuracies) / len(pipeline.cv_top3_accuracies))

        if pipeline.cv_top3_accuracies

        else None,

        "model_dir": str(model_dir.resolve()),

        "train_config": config.to_dict(),

    }


