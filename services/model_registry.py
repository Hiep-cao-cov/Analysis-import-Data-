"""Resolve and validate PMDI / TDI prediction model directories."""
from __future__ import annotations

from pathlib import Path

from config.settings import MODELS_DIR, PREDICTION_MODEL_OPTIONS, PROJECT_ROOT


def list_product_lines() -> list[str]:
    return list(PREDICTION_MODEL_OPTIONS.keys())


def _search_prefix_in_models_dir(prefix: str) -> list[Path]:
    if not MODELS_DIR.is_dir():
        return []
    found: list[Path] = []
    for child in sorted(MODELS_DIR.iterdir()):
        if child.is_dir() and prefix.upper() in child.name.upper():
            found.append(child)
    return found


def candidate_model_dirs(product_line: str) -> list[Path]:
    """All folders to check for a trained model (configured path first, then legacy / scan)."""
    key = product_line.upper()
    if key not in PREDICTION_MODEL_OPTIONS:
        raise KeyError(f"Unknown product line: {product_line}. Choose from {list_product_lines()}.")

    candidates: list[Path] = [Path(PREDICTION_MODEL_OPTIONS[key])]
    if key == "PMDI":
        candidates.extend(
            [
                PROJECT_ROOT / "production_material_predictor_muilti",
                MODELS_DIR / "production_material_predictor_muilti",
            ]
        )
        candidates.extend(_search_prefix_in_models_dir("MDI"))
    else:
        candidates.extend(
            [
                PROJECT_ROOT / "production_tdi_predictor",
                MODELS_DIR / "production_tdi_predictor",
            ]
        )
        candidates.extend(_search_prefix_in_models_dir("TDI"))

    seen: set[Path] = set()
    unique: list[Path] = []
    for path in candidates:
        resolved = path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(path)
    return unique


def resolve_model_dir(product_line: str) -> Path:
    """Return the first candidate folder that contains a complete trained model."""
    for path in candidate_model_dirs(product_line):
        if model_is_ready(path):
            return path
    return Path(PREDICTION_MODEL_OPTIONS[product_line.upper()])


def get_model_dir(product_line: str) -> Path:
    return resolve_model_dir(product_line)


def model_is_ready(model_dir: Path | str) -> bool:
    root = Path(model_dir)
    return (root / "model.pt").is_file() and (root / "pipeline_artifacts.joblib").is_file()


def model_status_message(model_dir: Path | str) -> str:
    root = Path(model_dir)
    if model_is_ready(root):
        return "Ready"
    if (root / "model.pt").is_file():
        return "Incomplete (missing pipeline_artifacts.joblib)"
    if not root.exists():
        return f"Folder not found: {root}"
    return "Not trained — train this product line first"


def model_status_for_product(product_line: str) -> tuple[Path, str]:
    """Resolved path + user-facing status (notes when a non-default folder is used)."""
    configured = Path(PREDICTION_MODEL_OPTIONS[product_line.upper()])
    resolved = resolve_model_dir(product_line)
    if model_is_ready(resolved):
        if resolved.resolve() != configured.resolve():
            return resolved, f"Ready · using `{resolved.name}`"
        return resolved, "Ready"
    return resolved, model_status_message(resolved)
