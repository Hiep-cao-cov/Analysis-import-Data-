"""Backward-compatible module aliases for pickled ML artifacts."""
from __future__ import annotations

import sys


def register_legacy_ml_module_aliases() -> None:
    """Models trained before the services/ layout pickle classes as k_fold_muilti_task.*."""
    from services import k_fold_muilti_task

    sys.modules["k_fold_muilti_task"] = k_fold_muilti_task
