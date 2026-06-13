"""User-adjustable training settings (passed from UI → train pipeline)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

from config.settings import (
    DEFAULT_MIN_SAMPLES_PER_CLASS,
    DEFAULT_MULTITASK_AUX_WEIGHT,
    DEFAULT_N_FOLDS,
    DEFAULT_RARE_CLASS_LABEL,
    DEFAULT_RANDOM_STATE,
    DEFAULT_TRAIN_BATCH_SIZE,
    DEFAULT_TRAIN_EPOCHS,
)


# merge: rare brands → single bucket label | drop: remove those rows from training
RARE_BRAND_MODE_MERGE = "merge"
RARE_BRAND_MODE_DROP = "drop"


@dataclass
class TrainConfig:
    min_samples_per_class: int = DEFAULT_MIN_SAMPLES_PER_CLASS
    rare_class_label: str = DEFAULT_RARE_CLASS_LABEL
    rare_brand_mode: str = RARE_BRAND_MODE_MERGE
    exclude_brands: list[str] = field(default_factory=list)
    auto_exclude_singletons: bool = True
    n_folds: int = DEFAULT_N_FOLDS
    epochs: int = DEFAULT_TRAIN_EPOCHS
    multitask_aux_weight: float = DEFAULT_MULTITASK_AUX_WEIGHT
    batch_size: int = DEFAULT_TRAIN_BATCH_SIZE
    random_state: int = DEFAULT_RANDOM_STATE
    word_tfidf_max: int = 500
    char_tfidf_max: int = 500

    def to_dict(self) -> dict:
        return asdict(self)
