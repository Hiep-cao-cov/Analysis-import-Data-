"""Train Model page: dataset summary + adjustable settings before training."""
from __future__ import annotations

from pathlib import Path

import streamlit as st

from config.settings import (
    DATA_DIR,
    DEFAULT_DATASET_FILENAMES,
    DEFAULT_MIN_SAMPLES_PER_CLASS,
    DEFAULT_MULTITASK_AUX_WEIGHT,
    DEFAULT_N_FOLDS,
    DEFAULT_RARE_CLASS_LABEL,
    DEFAULT_TRAIN_EPOCHS,
    MODELS_DIR,
    PREDICTION_MODEL_OPTIONS,
)
from services.data_paths import temp_file_path
from services.train_preview import analyze_training_dataset
from services.train_service import run_train
from services.training_config import RARE_BRAND_MODE_DROP, RARE_BRAND_MODE_MERGE, TrainConfig
from ui.theme import hero, section_header


def _resolve_train_path(train_upload, train_choice: str, train_files: list[str]) -> Path | None:
    if train_upload is not None:
        path = temp_file_path("train_upload", train_upload.name)
        path.write_bytes(train_upload.getvalue())
        return path
    if train_files and train_choice in train_files:
        return DATA_DIR / train_choice
    return None


def _preview_cache_key(path: Path, config: TrainConfig) -> str:
    stat = path.stat()
    excl = ",".join(sorted(config.exclude_brands))
    return (
        f"{path.resolve()}:{stat.st_mtime}:{stat.st_size}:"
        f"{config.min_samples_per_class}:{config.rare_class_label}:{config.rare_brand_mode}:"
        f"{config.auto_exclude_singletons}:{excl}:{config.n_folds}"
    )


def render_dataset_summary(summary, requested_folds: int) -> None:
    if summary.error:
        st.error(f"Could not load dataset: {summary.error}")
        return

    section_header("Dataset summary", f"`{summary.file_name}` · product line: **{summary.product_guess}**")
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Rows (trainable)", f"{summary.rows:,}")
    m2.metric("BRAND classes", summary.n_brand_after)
    m3.metric("Smallest class", summary.min_class_count)
    m4.metric("CV folds (effective)", summary.recommended_n_folds)
    m5.metric("Rows excluded", f"{summary.n_rows_excluded_brands:,}")

    st.caption(
        f"Brands before processing: **{summary.n_brand_before}** → after: **{summary.n_brand_after}** · "
        f"Largest class: **{summary.max_class_count:,}** rows"
    )

    if summary.singleton_brands and summary.recommended_n_folds < requested_folds:
        st.info(
            f"**{len(summary.singleton_brands)}** brand(s) still have only **1** row — that limits CV to "
            f"**{summary.recommended_n_folds}** folds. Enable **Remove 1-row brands** below or exclude them manually "
            f"to allow up to **{summary.recommended_n_folds_if_singletons_removed}** folds."
        )

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**Top brands (after rules)**")
        if summary.top_brands.empty:
            st.info("No brand counts.")
        else:
            st.dataframe(summary.top_brands, use_container_width=True, hide_index=True)
    with col_b:
        if summary.rare_brands:
            st.markdown("**Rare brands (merged or dropped)**")
            st.dataframe(
                {"BRAND NAME": [n for n, _ in summary.rare_brands], "rows": [c for _, c in summary.rare_brands]},
                use_container_width=True,
                hide_index=True,
            )
        if summary.singleton_brands:
            st.markdown("**Brands with only 1 row**")
            st.dataframe(
                {"BRAND NAME": [n for n, _ in summary.singleton_brands], "rows": [1] * len(summary.singleton_brands)},
                use_container_width=True,
                hide_index=True,
            )

    with st.expander("All brand counts", expanded=False):
        st.dataframe(
            {"BRAND NAME": [n for n, _ in summary.all_brand_counts], "rows": [c for _, c in summary.all_brand_counts]},
            use_container_width=True,
            hide_index=True,
        )


def render_train_settings_base() -> dict:
    """Settings that do not depend on brand multiselect."""
    section_header("Training settings", "Adjust then refresh summary.")
    c1, c2 = st.columns(2)
    with c1:
        min_samples = st.number_input(
            "Min rows per brand",
            min_value=1,
            max_value=50,
            value=int(st.session_state.get("train_min_samples", DEFAULT_MIN_SAMPLES_PER_CLASS)),
            key="train_min_samples",
        )
        rare_mode = st.radio(
            "Brands below minimum",
            options=[RARE_BRAND_MODE_MERGE, RARE_BRAND_MODE_DROP],
            format_func=lambda x: "Merge into rare bucket" if x == RARE_BRAND_MODE_MERGE else "Remove rows (exclude from training)",
            index=0 if st.session_state.get("train_rare_mode", RARE_BRAND_MODE_MERGE) == RARE_BRAND_MODE_MERGE else 1,
            key="train_rare_mode",
            help="Drop removes rows so they are not trained; merge keeps rows under one OTHER label (can still limit folds if OTHER has few rows).",
        )
        rare_label = st.text_input(
            "Rare bucket label (merge mode only)",
            value=st.session_state.get("train_rare_label", DEFAULT_RARE_CLASS_LABEL),
            key="train_rare_label",
            disabled=rare_mode == RARE_BRAND_MODE_DROP,
        )
        n_folds = st.slider("Cross-validation folds (requested)", 2, 10, int(st.session_state.get("train_n_folds", DEFAULT_N_FOLDS)), key="train_n_folds")
    with c2:
        auto_singletons = st.checkbox(
            "Remove brands with only 1 row (after rules above)",
            value=st.session_state.get("train_auto_singletons", True),
            key="train_auto_singletons",
            help="Recommended for TDI/small sets — removes single-row brands so CV can use more folds.",
        )
        epochs = st.slider("Max epochs (per fold)", 10, 120, int(st.session_state.get("train_epochs", DEFAULT_TRAIN_EPOCHS)), step=5, key="train_epochs")
        aux_weight = st.slider("TYPE / SUPPLIER loss weight", 0.0, 1.0, float(st.session_state.get("train_aux_weight", DEFAULT_MULTITASK_AUX_WEIGHT)), 0.05, key="train_aux_weight")
        batch_size = st.selectbox("Batch size", [64, 128, 256], index=1, key="train_batch_size")

    adv = st.expander("Advanced feature settings")
    with adv:
        w1, w2 = st.columns(2)
        with w1:
            word_max = st.number_input("Word TF-IDF features", 100, 2000, 500, step=50, key="train_word_max")
        with w2:
            char_max = st.number_input("Char TF-IDF features", 100, 2000, 500, step=50, key="train_char_max")

    return {
        "min_samples": int(min_samples),
        "rare_mode": rare_mode,
        "rare_label": str(rare_label).strip() or DEFAULT_RARE_CLASS_LABEL,
        "n_folds": int(n_folds),
        "auto_singletons": bool(auto_singletons),
        "epochs": int(epochs),
        "aux_weight": float(aux_weight),
        "batch_size": int(batch_size),
        "word_max": int(word_max),
        "char_max": int(char_max),
    }


def render_brand_exclusion_multiselect(all_brands: list[tuple[str, int]]) -> list[str]:
    section_header("Exclude brands from training", "Optional — removes all rows for selected brands.")
    options = [f"{name} ({count} rows)" for name, count in all_brands]
    name_by_label = {f"{name} ({count} rows)": name for name, count in all_brands}
    default_labels = st.session_state.get("train_exclude_labels", [])
    picked = st.multiselect(
        "Brands to exclude",
        options=options,
        default=[x for x in default_labels if x in options],
        key="train_exclude_multiselect",
        help="Tip: exclude 1-row brands here instead of using only 2-fold CV.",
    )
    st.session_state.train_exclude_labels = picked
    return [name_by_label[lbl] for lbl in picked]


def build_train_config(base: dict, exclude_brands: list[str]) -> TrainConfig:
    return TrainConfig(
        min_samples_per_class=base["min_samples"],
        rare_class_label=base["rare_label"],
        rare_brand_mode=base["rare_mode"],
        exclude_brands=exclude_brands,
        auto_exclude_singletons=base["auto_singletons"],
        n_folds=base["n_folds"],
        epochs=base["epochs"],
        multitask_aux_weight=base["aux_weight"],
        batch_size=base["batch_size"],
        word_tfidf_max=base["word_max"],
        char_tfidf_max=base["char_max"],
    )


def render_train_page(list_data_files_fn) -> None:
    hero("Train Model", "Review data, exclude rare brands if needed, then train.")

    train_files = [f.name for f in list_data_files_fn() if "dataset" in f.name.lower() or "final" in f.name.lower()]
    default_seed = DEFAULT_DATASET_FILENAMES["MDI"]
    default_idx = train_files.index(default_seed) if default_seed in train_files else 0

    col_data, col_model = st.columns([1, 1])
    with col_data:
        section_header("Training data", "BRAND NAME, TYPE, SUPPLIER required")
        train_choice = st.selectbox("Dataset file", train_files or ["(no files)"], index=default_idx if train_files else 0, key="train_file_choice")
        train_upload = st.file_uploader("Or upload labeled CSV", type=["csv"], key="train_upload")
    with col_model:
        section_header("Model output")
        train_product = st.radio(
            "Save as product line",
            options=list(PREDICTION_MODEL_OPTIONS.keys()),
            horizontal=True,
            key="train_product_line",
            help="Must match the line you select later in Predict new.",
        )
        default_folder = PREDICTION_MODEL_OPTIONS[train_product].name
        model_name = st.text_input("Model folder name", value=default_folder, key="train_model_name")
        preset = PREDICTION_MODEL_OPTIONS[train_product]
        model_dir = preset if model_name == preset.name else MODELS_DIR / model_name
        st.text_input("Save to", value=str(model_dir), disabled=True)

    base = render_train_settings_base()
    path = _resolve_train_path(train_upload, train_choice, train_files)

    refresh = st.button("Refresh dataset summary", use_container_width=True)

    # First pass config (no manual excludes) for initial load / cache
    preview_config = build_train_config(base, st.session_state.get("train_manual_excludes", []))
    summary = None
    if path is not None:
        cache_key = _preview_cache_key(path, preview_config)
        if refresh or st.session_state.get("train_preview_key") != cache_key:
            with st.spinner("Loading dataset and building summary…"):
                summary = analyze_training_dataset(path, preview_config)
            st.session_state.train_preview_key = cache_key
            st.session_state.train_preview_summary = summary
            st.session_state.train_all_brands = summary.all_brand_counts
        else:
            summary = st.session_state.get("train_preview_summary")

    exclude_brands: list[str] = []
    if summary is not None and not summary.error and st.session_state.get("train_all_brands"):
        exclude_brands = render_brand_exclusion_multiselect(st.session_state.train_all_brands)
        st.session_state.train_manual_excludes = exclude_brands
        st.caption("Change exclusions then click **Refresh dataset summary** to update fold counts.")

    train_config = build_train_config(base, exclude_brands)

    if summary is not None:
        render_dataset_summary(summary, train_config.n_folds)
        if summary.error is None and train_config.n_folds > summary.recommended_n_folds:
            st.warning(
                f"Requested **{train_config.n_folds}** folds; training will use **{summary.recommended_n_folds}** "
                f"(smallest class has **{summary.min_class_count}** row(s))."
            )
    elif path is None:
        st.info("Select or upload a training file.")
    else:
        st.info("Click **Refresh dataset summary**.")

    st.markdown("---")
    start_disabled = path is None or (summary is not None and summary.error is not None)

    if st.button("Start training", type="primary", use_container_width=True, disabled=start_disabled):
        try:
            train_config = build_train_config(base, exclude_brands)
            progress_bar = st.progress(0.0, text="Starting…")
            status_line = st.empty()

            def on_train_progress(fraction: float, message: str) -> None:
                progress_bar.progress(fraction, text=f"{int(fraction * 100)}% — {message[:80]}")
                status_line.markdown(f"**Current step:** {message}")

            with st.status("Training in progress…", expanded=True) as train_status:
                st.caption(f"`{path.name}` · {train_config.rare_brand_mode} · max epochs **{train_config.epochs}**")
                out = run_train(path, model_dir, config=train_config, progress_callback=on_train_progress)
                train_status.update(label="Training finished", state="complete")

            progress_bar.progress(1.0, text="100% — Complete")
            st.session_state.model_dir = out["model_dir"]
            st.success("Training finished.")
            c1, c2, c3 = st.columns(3)
            c1.metric("Rows", f"{out['rows']:,}")
            c2.metric("Classes", out["classes"])
            if out["mean_cv_accuracy"] is not None:
                c3.metric("Mean CV accuracy", f"{out['mean_cv_accuracy']:.2%}")
        except Exception as e:
            st.error(f"Training failed: {e}")
