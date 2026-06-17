"""User data, app seed datasets, temp uploads, and file listing helpers."""
from __future__ import annotations

import shutil
from pathlib import Path

from config.settings import (
    APP_CONFIG_DIR,
    APP_REFERENCE_DATA_FILENAMES,
    DATA_DIR,
    DEFAULT_DATASET_FILENAMES,
    DEFAULT_DATASETS_DIR,
    TEMP_DIR,
)


def ensure_storage_dirs() -> None:
    """Create data/, app_data/, temp/, app_config/ if missing."""
    for folder in (DATA_DIR, DEFAULT_DATASETS_DIR, TEMP_DIR, APP_CONFIG_DIR):
        folder.mkdir(parents=True, exist_ok=True)


def normalize_dataset_mode(mode: str) -> str:
    m = str(mode).strip().upper()
    if m == "PMDI":
        return "MDI"
    if m in DEFAULT_DATASET_FILENAMES:
        return m
    return "MDI"


def seed_dataset_path(mode: str) -> Path:
    """Read-only app default dataset (MDI / TDI seed files in app_data/)."""
    key = normalize_dataset_mode(mode)
    return DEFAULT_DATASETS_DIR / DEFAULT_DATASET_FILENAMES[key]


def default_dashboard_dataset_path(mode: str) -> Path:
    """
    Dataset for **Use default file** dashboards (MDI and TDI).
    Always the app_data seed — never the merged copy under data/.
    """
    return seed_dataset_path(mode)


def is_seed_dataset_path(path: Path) -> bool:
    """True when path is an app_data seed file (not a user copy under data/)."""
    resolved = Path(path).resolve()
    return any(
        (DEFAULT_DATASETS_DIR / name).resolve() == resolved
        for name in DEFAULT_DATASET_FILENAMES.values()
    )


def resolve_analysis_dataset(mode: str) -> Path:
    """Dataset used for analysis/merge base (always app_data seed)."""
    return seed_dataset_path(mode)


def analysis_dataset_save_path(mode: str) -> Path:
    """Where Import Analytics merge writes (same default seed file)."""
    return seed_dataset_path(mode)


def temp_file_path(prefix: str, filename: str) -> Path:
    """Temporary upload / predict staging file under temp/."""
    ensure_storage_dirs()
    safe_name = Path(filename).name
    return TEMP_DIR / f"_{prefix}_{safe_name}"


_temp_dir_cleared = False


def clear_temp_dir_on_startup() -> None:
    """Delete all files in temp/ once per Streamlit server process (not each rerun)."""
    global _temp_dir_cleared
    if _temp_dir_cleared:
        return
    _temp_dir_cleared = True

    ensure_storage_dirs()
    if not TEMP_DIR.is_dir():
        return

    for path in TEMP_DIR.iterdir():
        if path.name == ".gitkeep":
            continue
        try:
            if path.is_file() or path.is_symlink():
                path.unlink()
            elif path.is_dir():
                shutil.rmtree(path)
        except OSError:
            continue


def migrate_storage_layout() -> None:
    """
    One-time layout fix: seed CSVs → app_data/, temp _* files → temp/,
    reference CSVs → app_config/.
    """
    ensure_storage_dirs()
    project_data = DATA_DIR

    for mode, filename in DEFAULT_DATASET_FILENAMES.items():
        src = project_data / filename
        dst = DEFAULT_DATASETS_DIR / filename
        if src.is_file() and not dst.is_file():
            shutil.move(str(src), str(dst))

    for name in APP_REFERENCE_DATA_FILENAMES:
        src = project_data / name
        dst = APP_CONFIG_DIR / name
        if src.is_file() and not dst.is_file():
            shutil.move(str(src), str(dst))
        elif src.is_file() and dst.is_file():
            src.unlink()

    if project_data.exists():
        for p in project_data.iterdir():
            if p.is_file() and p.name.startswith("_"):
                target = TEMP_DIR / p.name
                try:
                    if target.exists():
                        p.unlink()
                    else:
                        shutil.move(str(p), str(target))
                except OSError:
                    continue
