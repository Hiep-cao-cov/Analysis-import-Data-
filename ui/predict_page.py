"""Predict new — choose PMDI or TDI model, run inference, download results."""
from __future__ import annotations

from pathlib import Path

import streamlit as st

from config.settings import ANALYSIS_HS_CODE_OPTIONS, DATA_DIR, PREDICT_CONFIDENCE_COLUMNS, TEMP_DIR
from services.model_registry import (
    list_product_lines,
    model_is_ready,
    model_status_for_product,
    resolve_model_dir,
)
from services.predict_prepare import (
    DELETE_REASON_COL,
    MARK_FOR_DELETE_COL,
    filter_predict_download_options,
)
from services.predict_service import run_predict
from ui.theme import hero, section_header


def clear_predict_workspace() -> None:
    """Reset Predict new page for a fresh file and empty results table."""
    for key in (
        "last_predictions",
        "last_predictions_product",
        "last_predict_filter_stats",
        "predict_source_path",
        "active_df",
        "active_df_name",
    ):
        st.session_state[key] = None

    for widget_key in (
        "predict_upload",
        "predict_file_select",
        "predict_use_session",
        "predict_download_exclude_marked",
        "predict_download_include_confidence",
    ):
        st.session_state.pop(widget_key, None)


def render_model_selector() -> Path:
    """Product-line model picker; returns resolved model directory."""
    section_header("Prediction model", "Use the model trained for the same product line as your data.")

    lines = list_product_lines()
    current = st.session_state.get("predict_product_line", "PMDI")
    if current not in lines:
        current = lines[0]

    product_line = st.radio(
        "Product line",
        options=lines,
        index=lines.index(current),
        horizontal=True,
        key="predict_product_line",
        help="PMDI = polymeric MDI brands · TDI = toluene diisocyanate brands",
    )

    model_dir, status = model_status_for_product(product_line)
    st.session_state.model_dir = str(model_dir)

    ready = model_is_ready(model_dir)
    c1, c2 = st.columns([2, 1])
    with c1:
        st.text_input("Model folder", value=str(model_dir), disabled=True)
    with c2:
        if ready:
            st.success(status)
        else:
            st.warning(status)

    with st.expander("Custom model folder (optional)"):
        use_custom = st.checkbox("Override folder path", value=False, key="predict_use_custom_model")
        if use_custom:
            custom = st.text_input(
                "Custom path",
                value=st.session_state.get("predict_custom_model_dir", str(model_dir)),
                key="predict_custom_model_dir",
            )
            if custom.strip():
                model_dir = Path(custom.strip())
                st.session_state.model_dir = str(model_dir)
                if model_is_ready(model_dir):
                    st.success("Ready")
                else:
                    from services.model_registry import model_status_message

                    st.warning(model_status_message(model_dir))

    hs = ANALYSIS_HS_CODE_OPTIONS.get(product_line, [])
    if hs:
        st.caption(f"Raw file ETL uses **{product_line}** HS codes ({len(hs)} codes) when features need standardizing.")

    return model_dir


def render_predict_page(load_dataset_selector, set_active_df) -> None:
    hero("Prediction", "Select PMDI or TDI model, then fill BRAND NAME, TYPE, and SUPPLIER on import data.")

    model_dir = render_model_selector()
    product_line = st.session_state.get("predict_product_line", "PMDI")

    st.markdown("---")
    st.caption(
        "Every input row is kept in the output. Rows that fail a rule are **marked** in "
        "`marked_for_delete` with a detailed `delete_reason` (not removed). "
        "Use the download checkbox to export with or without marked rows. "
        "Upload the download in **Import Analytics → Upload new file → Update data** "
        "to merge into your MDI/TDI dataset (same format as the default analysis files)."
    )
    result = load_dataset_selector("predict")
    if result[0] is None:
        st.info("Upload raw customs or standardized CSV/Excel. Output columns: BRAND NAME, SUPPLIER, TYPE.")
        return

    df, name = result
    if st.button("Run prediction", type="primary", use_container_width=True):
        if not model_is_ready(model_dir):
            st.error(
                f"{product_line} model not ready in `{model_dir}`. "
                f"Expected `models/{'MDI' if product_line == 'PMDI' else 'TDI'}_production_material_predictor_muilti` "
                f"with `model.pt` and `pipeline_artifacts.joblib`."
            )
        else:
            try:
                source_path = st.session_state.get("predict_source_path")
                if not source_path and name:
                    for folder in (DATA_DIR, TEMP_DIR):
                        candidate = folder / name
                        if candidate.is_file():
                            source_path = str(candidate)
                            break

                with st.status(
                    f"Running {product_line} prediction on **{name}** ({len(df):,} rows)…",
                    expanded=True,
                ) as status_box:
                    progress_bar = st.progress(0.0, text="Starting…")
                    step_lines: list[str] = []
                    step_log = st.empty()

                    def on_predict_progress(pct: float, message: str) -> None:
                        progress_bar.progress(pct, text=message)
                        if not step_lines or step_lines[-1] != message:
                            step_lines.append(message)
                        step_log.markdown(
                            "\n".join(
                                f"{'✅' if i < len(step_lines) - 1 else '⏳'} {line}"
                                for i, line in enumerate(step_lines)
                            )
                        )

                    out, filter_stats = run_predict(
                        df,
                        model_dir,
                        source_path=source_path,
                        product_line=product_line,
                        progress_callback=on_predict_progress,
                    )
                    progress_bar.progress(1.0, text="Prediction complete")
                    step_log.markdown("\n".join(f"✅ {line}" for line in step_lines))
                    status_box.update(
                        label=f"Prediction complete — {len(out):,} rows · {product_line} model",
                        state="complete",
                        expanded=False,
                    )

                st.session_state.last_predictions = out
                st.session_state.last_predictions_product = product_line
                st.session_state.last_predict_filter_stats = filter_stats
                set_active_df(out, f"{name} ({product_line} predictions)")
                st.success(f"Done — {len(out):,} rows · model: **{product_line}**")
                for line in filter_stats.summary_lines():
                    st.caption(line)
            except Exception as e:
                st.error(f"Prediction failed: {e}")

    if st.session_state.last_predictions is not None:
        from config.settings import COL_BRAND_NAME, COL_SUPPLIER, COL_TYPE, PREDICT_CONFIDENCE_COLUMNS

        out = st.session_state.last_predictions
        pl = st.session_state.get("last_predictions_product", product_line)
        show_cols = [
            c
            for c in (
                MARK_FOR_DELETE_COL,
                DELETE_REASON_COL,
                COL_BRAND_NAME,
                COL_SUPPLIER,
                COL_TYPE,
                *PREDICT_CONFIDENCE_COLUMNS,
                "description",
                "hs_code",
            )
            if c in out.columns
        ]
        st.caption(
            f"Showing results from **{pl}** model · "
            "Confidence = softmax probability of the predicted class (0–1)."
        )
        st.dataframe(out[show_cols].head(500), use_container_width=True)

        exclude_marked = st.checkbox(
            "Download without rows marked for deletion",
            value=False,
            key="predict_download_exclude_marked",
            help="When checked, rows with marked_for_delete = Yes are omitted from the CSV.",
        )
        include_confidence = st.checkbox(
            "Include confidence scores in download",
            value=True,
            key="predict_download_include_confidence",
            help="Adds brand_confidence, type_confidence, supplier_confidence columns (0–1).",
        )
        download_df = filter_predict_download_options(
            out,
            exclude_marked=exclude_marked,
            include_confidence=include_confidence,
        )
        n_marked = 0
        if MARK_FOR_DELETE_COL in out.columns:
            n_marked = int((out[MARK_FOR_DELETE_COL].astype(str).str.strip().str.lower() == "yes").sum())
        dl_label = f"Download predictions ({len(download_df):,} rows"
        if exclude_marked and n_marked:
            dl_label += f", {n_marked:,} marked rows excluded"
        dl_label += ")"
        csv_bytes = download_df.to_csv(index=False).encode("utf-8-sig")
        col_download, col_clear = st.columns([3, 1])
        with col_download:
            st.download_button(
                dl_label,
                csv_bytes,
                file_name=f"predictions_{pl.lower()}.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with col_clear:
            if st.button(
                "Clear & new file",
                key="predict_clear_results_btn",
                use_container_width=True,
                help="Clear prediction results and reset file selection for a new upload.",
            ):
                clear_predict_workspace()
                st.rerun()
