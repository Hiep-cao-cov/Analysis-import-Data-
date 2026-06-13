import os
import re
from collections import Counter
from typing import Callable
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from sklearn.model_selection import StratifiedKFold, KFold
from sklearn.preprocessing import LabelEncoder, MinMaxScaler
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import accuracy_score, top_k_accuracy_score, classification_report
import joblib
import torch.nn.functional as F

# ══════════════════════════════════════════════
# 0. DYNAMIC COLUMN CONFIGURATION STRUCTURE
# ══════════════════════════════════════════════

class ColumnConfig:
    """Configures explicit custom mapping rules for dataset columns."""
    def __init__(self, hs_code: str, product_description: str, saler: str, country_origin: str,
                 label: str, type_col: str = None, supplier_col: str = None):
        self.hs_code = hs_code
        self.product_description = product_description
        self.saler = saler
        self.country_origin = country_origin
        self.label = label
        self.type_col = type_col
        self.supplier_col = supplier_col

    def validate(self, df: pd.DataFrame, require_targets: bool = True):
        required = [self.hs_code, self.product_description, self.saler, self.country_origin]
        if require_targets:
            required.append(self.label)
            if self.type_col: required.append(self.type_col)
            if self.supplier_col: required.append(self.supplier_col)
            
        for col in required:
            if col not in df.columns:
                raise ValueError(f"Target execution column '{col}' missing from your DataFrame mapping.")


# ══════════════════════════════════════════════
# 1. TEXT CLEANING & FEATURE HELPERS
# ══════════════════════════════════════════════

CAS_PATTERN = re.compile(r'\b\d+(?:[_\-]\d+)+\b')
LONG_NUM_PATTERN = re.compile(r'\b\d{6,}\b')

CHEMICAL_KEYWORDS = [
    "isocyanate", "polyurethane", "polyurethan", "polymer", "resin",
    "compound", "methylene", "polyphenyl", "prepolymer",
    "polyol", "mdi", "tdi", "cas", "pu", "polyester",
    "polycarbonate", "epoxy", "hardener", "catalyst",
]

BRAND_KEYWORDS = [
    "suprasec", "desmodur", "desmophen", "daltoped", "daltocast",
    "mondur", "vibrathane", "imuthane", "sup", "jf",
    "coronate", "wannate", "elastopan", "papi", "mp", "44v20l", "44v20", "44v",
    "cosmonate", "elastopor", "luraphen", "zh", "mr", "mr200", "m20", "m20s", "mr-200",
    "kw", "cg", "nelilon", "urecom", "iso", "zlf", "cpu", "pm-2010", "pm2010",
    "ku", "mdi", "koniso", "eterane", "elastofoam", "isocyante", "h3610", "910",
    "yf", "isocxyanates", "pah", "jhw", "m200", "pm200", "pm400", "pm-200", "m-200"
]


def clean_description(text: str) -> str:
    """Normalize raw product description for TF-IDF."""
    if not isinstance(text, str):
        return ""
    text = text.lower()
    text = CAS_PATTERN.sub(" <cas> ", text)
    text = LONG_NUM_PATTERN.sub(" <code> ", text)
    text = re.sub(r"[/_\\]", " ", text)
    text = re.sub(r"[^a-z0-9<>\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def fix_scientific_notation(val):
    """Convert Excel scientific notation string artifacts back to clean integers."""
    if not isinstance(val, str):
        return val
    val = val.replace("'", "").strip()
    if 'e' in val.lower() and '+' in val:
        try:
            return str(int(float(val)))
        except ValueError:
            return val
    return val


def add_keyword_flags(df: pd.DataFrame, col: str = "product_description_clean") -> pd.DataFrame:
    """Binary flags for chemistry terms + brand names + structural patterns."""
    for kw in CHEMICAL_KEYWORDS:
        df[f"kw_{kw}"] = df[col].str.contains(kw, case=False).astype(np.int8)
    for brand in BRAND_KEYWORDS:
        df[f"brand_{brand}"] = df[col].str.contains(brand, case=False).astype(np.int8)

    df["has_cas"] = df[col].str.contains("<cas>").astype(np.int8)
    df["has_code"] = df[col].str.contains("<code>").astype(np.int8)

    df["product_code_count"] = df[col].apply(
        lambda x: len(re.findall(r'\b(\d+[a-z]+\d*[a-z]*|\d{3,5}|[a-z]\d{3,}[a-z]*)\b', x))
    ).astype(np.int8)

    df["brand_count"] = df[[f"brand_{b}" for b in BRAND_KEYWORDS]].sum(axis=1).astype(np.int8)
    df["desc_word_count"] = df[col].apply(lambda x: len(x.split())).astype(np.int16)

    return df


def expand_hs_code(df: pd.DataFrame, hs_col_name: str) -> pd.DataFrame:
    """Extract HS code hierarchy levels."""
    hs = df[hs_col_name].astype(str).str.zfill(8)
    df["hs_chapter"] = hs.str[:2]
    df["hs_heading"] = hs.str[:4]
    df["hs_subheading"] = hs.str[:6]
    df["hs_full"] = hs
    return df


def frequency_encode(series: pd.Series, freq_map: dict = None):
    if freq_map is None:
        freq_map = series.value_counts(normalize=True).to_dict()
    return series.map(freq_map).fillna(0.0), freq_map


# ══════════════════════════════════════════════
# 2. ENHANCED FEATURE TRANSFORMER
# ══════════════════════════════════════════════

class EnhancedFeatureTransformer:
    def __init__(self, config: ColumnConfig, word_tfidf_max=500, char_tfidf_max=500,
                 word_ngram=(1, 2), char_ngram=(3, 5)):
        self.config = config
        self.word_tfidf_max = word_tfidf_max
        self.char_tfidf_max = char_tfidf_max
        self.word_ngram = word_ngram
        self.char_ngram = char_ngram

        self.word_tfidf_ = None
        self.char_tfidf_ = None
        self.scaler_ = None
        self.saler_freq_map_ = None
        self.hs_chapter_le_ = None
        self.hs_heading_le_ = None
        self.hs_subheading_le_ = None
        self.hs_full_le_ = None
        self.country_dummies_cols_ = None
        self.keyword_cols_ = None
        self.feature_names_ = None

    def fit_transform(self, df: pd.DataFrame) -> np.ndarray:
        df = df.copy()
        col = self.config

        # HS Code Encoding
        df = expand_hs_code(df, col.hs_code)
        self.hs_chapter_le_ = LabelEncoder().fit(df["hs_chapter"])
        self.hs_heading_le_ = LabelEncoder().fit(df["hs_heading"])
        self.hs_subheading_le_ = LabelEncoder().fit(df["hs_subheading"])
        self.hs_full_le_ = LabelEncoder().fit(df["hs_full"])
        hs_feats = self._encode_hs(df)

        # Product Description Flagging
        df["product_description_clean"] = df[col.product_description].apply(clean_description)
        df = add_keyword_flags(df)

        self.keyword_cols_ = [c for c in df.columns if c.startswith("kw_") or c.startswith("brand_") or c in (
            "has_cas", "has_code", "product_code_count", "brand_count", "desc_word_count")]
        kw_feats = df[self.keyword_cols_].values.astype(np.float32)

        # Word-Level Extraction
        self.word_tfidf_ = TfidfVectorizer(
            max_features=self.word_tfidf_max, ngram_range=self.word_ngram,
            analyzer='word', sublinear_tf=True, min_df=2, max_df=0.95,
        )
        word_tfidf_feats = self.word_tfidf_.fit_transform(df["product_description_clean"]).toarray()

        # Char-Level Extraction
        self.char_tfidf_ = TfidfVectorizer(
            max_features=self.char_tfidf_max, ngram_range=self.char_ngram,
            analyzer='char_wb', sublinear_tf=True, min_df=2, max_df=0.95,
        )
        char_tfidf_feats = self.char_tfidf_.fit_transform(df["product_description_clean"]).toarray()

        # Saler Frequency (Fixing Leakage: No Target Mapping Here)
        saler_freq, self.saler_freq_map_ = frequency_encode(df[col.saler])
        saler_feats = saler_freq.values.reshape(-1, 1).astype(np.float32)

        # Country Mapping
        country_dummies = pd.get_dummies(df[col.country_origin], prefix="country")
        self.country_dummies_cols_ = list(country_dummies.columns)
        country_feats = country_dummies.values.astype(np.float32)

        X = np.concatenate([hs_feats, word_tfidf_feats, char_tfidf_feats, kw_feats, saler_feats, country_feats], axis=1)

        self.scaler_ = MinMaxScaler()
        X = self.scaler_.fit_transform(X).astype(np.float32)

        hs_names = ["hs_chapter_enc", "hs_heading_enc", "hs_subheading_enc", "hs_full_enc"]
        word_names = [f"word_tfidf_{v}" for v in self.word_tfidf_.get_feature_names_out()]
        char_names = [f"char_tfidf_{v}" for v in self.char_tfidf_.get_feature_names_out()]
        self.feature_names_ = hs_names + word_names + char_names + self.keyword_cols_ + ["saler_freq"] + self.country_dummies_cols_

        return X

    def transform(self, df: pd.DataFrame) -> np.ndarray:
        df = df.copy()
        col = self.config

        df = expand_hs_code(df, col.hs_code)
        hs_feats = self._encode_hs(df)

        df["product_description_clean"] = df[col.product_description].apply(clean_description)
        df = add_keyword_flags(df)
        kw_feats = df[self.keyword_cols_].values.astype(np.float32)

        word_tfidf_feats = self.word_tfidf_.transform(df["product_description_clean"]).toarray()
        char_tfidf_feats = self.char_tfidf_.transform(df["product_description_clean"]).toarray()

        saler_freq = df[col.saler].map(self.saler_freq_map_).fillna(0.0)
        saler_feats = saler_freq.values.reshape(-1, 1).astype(np.float32)

        country_dummies = pd.get_dummies(df[col.country_origin], prefix="country")
        for c_col in self.country_dummies_cols_:
            if c_col not in country_dummies.columns:
                country_dummies[c_col] = 0
        country_feats = country_dummies[self.country_dummies_cols_].values.astype(np.float32)

        X = np.concatenate([hs_feats, word_tfidf_feats, char_tfidf_feats, kw_feats, saler_feats, country_feats], axis=1)
        return self.scaler_.transform(X).astype(np.float32)

    def _encode_hs(self, df: pd.DataFrame) -> np.ndarray:
        def safe_transform(le, series):
            known = set(le.classes_)
            return le.transform(series.map(lambda x: x if x in known else le.classes_[0]))
        return np.stack([
            safe_transform(self.hs_chapter_le_, df["hs_chapter"]),
            safe_transform(self.hs_heading_le_, df["hs_heading"]),
            safe_transform(self.hs_subheading_le_, df["hs_subheading"]),
            safe_transform(self.hs_full_le_, df["hs_full"]),
        ], axis=1).astype(np.float32)

    @property
    def num_features(self):
        return len(self.feature_names_)


def balanced_class_weights(y: np.ndarray, num_classes: int) -> np.ndarray:
    """
    Balanced weights for CrossEntropyLoss — one weight per class index 0..num_classes-1.
    Folds that omit a rare class still get a full-length tensor (missing → mean weight).
    """
    y = np.asarray(y, dtype=np.int64)
    counts = np.bincount(y, minlength=num_classes).astype(np.float64)
    weights = np.ones(num_classes, dtype=np.float64)
    present = counts > 0
    if not present.any():
        return weights.astype(np.float32)
    n_samples = counts[present].sum()
    n_present = int(present.sum())
    weights[present] = n_samples / (n_present * counts[present])
    weights[~present] = weights[present].mean()
    return weights.astype(np.float32)


# ══════════════════════════════════════════════
# 3. NEURAL NETWORK ARCHITECTURE (Multi-Task Capable)
# ══════════════════════════════════════════════

class ResidualBlock(nn.Module):
    def __init__(self, dim, dropout=0.3):
        super().__init__()
        self.block = nn.Sequential(
            nn.Linear(dim, dim), nn.BatchNorm1d(dim), nn.ReLU(), nn.Dropout(dropout),
            nn.Linear(dim, dim), nn.BatchNorm1d(dim)
        )
        self.relu = nn.ReLU()

    def forward(self, x):
        return self.relu(x + self.block(x))


class MaterialPredictor(nn.Module):
    def __init__(self, num_features, num_classes_label, num_classes_type=None, num_classes_supplier=None, dropout=0.3):
        super().__init__()
        self.use_multitask = num_classes_type is not None and num_classes_supplier is not None

        # Shared Feature backbone
        self.shared_network = nn.Sequential(
            nn.BatchNorm1d(num_features),
            nn.Linear(num_features, 512), nn.BatchNorm1d(512), nn.ReLU(), nn.Dropout(dropout),
            ResidualBlock(512, dropout),
            nn.Linear(512, 256), nn.BatchNorm1d(256), nn.ReLU(), nn.Dropout(dropout),
            ResidualBlock(256, dropout),
            nn.Linear(256, 128), nn.BatchNorm1d(128), nn.ReLU(), nn.Dropout(dropout * 0.7),
        )

        # Dynamic Task Output Heads
        self.label_head = nn.Linear(128, num_classes_label)
        if self.use_multitask:
            self.type_head = nn.Linear(128, num_classes_type)
            self.supplier_head = nn.Linear(128, num_classes_supplier)

    def forward(self, x):
        features = self.shared_network(x)
        logits_label = self.label_head(features)
        if self.use_multitask:
            return logits_label, self.type_head(features), self.supplier_head(features)
        return logits_label


# ══════════════════════════════════════════════
# 4. ROBUST K-FOLD COMPREHENSIVE PIPELINE
# ══════════════════════════════════════════════

class MaterialPredictionPipeline:
    def __init__(
        self,
        column_config: ColumnConfig,
        word_tfidf_max=500,
        char_tfidf_max=500,
        n_folds=5,
        random_state=42,
        use_multitask=False,
        device=None,
        min_samples_per_class: int = 5,
        rare_class_label: str | None = None,
        rare_brand_mode: str = "merge",
        exclude_brands: list | None = None,
        auto_exclude_singletons: bool = True,
        multitask_aux_weight: float = 0.4,
    ):
        self.column_config = column_config
        self.word_tfidf_max = word_tfidf_max
        self.char_tfidf_max = char_tfidf_max
        self.n_folds = n_folds
        self.random_state = random_state
        self.use_multitask = use_multitask
        self.min_samples_per_class = min_samples_per_class
        from config.settings import DEFAULT_RARE_CLASS_LABEL

        self.rare_class_label = rare_class_label or DEFAULT_RARE_CLASS_LABEL
        self.rare_brand_mode = rare_brand_mode
        self.exclude_brands = list(exclude_brands or [])
        self.auto_exclude_singletons = auto_exclude_singletons
        self.multitask_aux_weight = multitask_aux_weight
        self.device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # Transformers and Encoders
        self.feature_transformer = None
        self.model = None
        self.label_encoder = None
        self.type_encoder = None
        self.supplier_encoder = None

        # Metric Cache
        self.cv_accuracies = []
        self.cv_top3_accuracies = []

    def load_and_prepare(self, filepath: str) -> pd.DataFrame:
        from services.data_loader_service import load_for_ml

        df = load_for_ml(filepath)
        col = self.column_config
        col.validate(df, require_targets=True)

        # Format Conversions & Standard Cleaning
        df[col.product_description] = df[col.product_description].apply(fix_scientific_notation)
        df[col.hs_code] = df[col.hs_code].astype(str).str.zfill(8)
        df[col.saler] = df[col.saler].fillna("UNKNOWN")
        df[col.country_origin] = df[col.country_origin].fillna("UNKNOWN")
        df[col.label] = df[col.label].astype(str).str.strip()
        
        if self.use_multitask:
            df[col.type_col] = df[col.type_col].astype(str).str.strip()
            df[col.supplier_col] = df[col.supplier_col].astype(str).str.strip()

        # Filter Essential NaNs
        df.dropna(subset=[col.hs_code, col.product_description, col.label], inplace=True)

        from services.train_preview import apply_brand_training_rules
        from services.training_config import TrainConfig

        prep_config = TrainConfig(
            min_samples_per_class=self.min_samples_per_class,
            rare_class_label=self.rare_class_label,
            rare_brand_mode=self.rare_brand_mode,
            exclude_brands=self.exclude_brands,
            auto_exclude_singletons=self.auto_exclude_singletons,
        )
        df, brand_stats = apply_brand_training_rules(df, col.label, prep_config)
        if len(df) == 0:
            raise ValueError(
                "No training rows left after brand exclusions. "
                "Reduce min samples per brand or clear excluded brands."
            )
        if brand_stats.rows_removed:
            print(f"[INFO] Excluded {brand_stats.rows_removed:,} rows via brand rules.")

        print(f"{'='*60}\nDATA LOAD COMPLETED SUCCESSFULLY\n{'='*60}")
        print(f"  Rows Extracted: {len(df)} | Unique Classes: {df[col.label].nunique()}")
        return df.reset_index(drop=True)

    def train(
        self,
        df: pd.DataFrame,
        epochs=120,
        lr=0.0008,
        batch_size=128,
        dropout=0.3,
        patience_limit=25,
        progress_callback: Callable[[float, str], None] | None = None,
    ):
        df = df.copy()
        col = self.column_config

        def report(fraction: float, message: str) -> None:
            print(message)
            if progress_callback is not None:
                progress_callback(min(1.0, max(0.0, fraction)), message)

        report(0.20, "Encoding labels (BRAND NAME, TYPE, SUPPLIER)…")

        # Target Label Mapping
        self.label_encoder = LabelEncoder()
        y_label = self.label_encoder.fit_transform(df[col.label])
        num_classes_label = len(self.label_encoder.classes_)

        num_classes_type, num_classes_supplier = None, None
        y_type, y_supplier = None, None

        if self.use_multitask:
            self.type_encoder = LabelEncoder()
            self.supplier_encoder = LabelEncoder()
            y_type = self.type_encoder.fit_transform(df[col.type_col])
            y_supplier = self.supplier_encoder.fit_transform(df[col.supplier_col])
            num_classes_type = len(self.type_encoder.classes_)
            num_classes_supplier = len(self.supplier_encoder.classes_)

        # Vector Processing Setup
        self.feature_transformer = EnhancedFeatureTransformer(
            self.column_config, word_tfidf_max=self.word_tfidf_max, char_tfidf_max=self.char_tfidf_max
        )
        report(0.28, "Building TF-IDF and numeric features…")
        X = self.feature_transformer.fit_transform(df)
        num_features = X.shape[1]
        report(0.32, f"Feature matrix ready · {num_features:,} features · device: {self.device}")

        from services.train_preview import effective_n_folds

        min_class_count = int(pd.Series(y_label).value_counts().min())
        n_splits = effective_n_folds(self.n_folds, min_class_count)
        if n_splits != self.n_folds:
            print(f"[INFO] Using {n_splits}-fold CV (requested {self.n_folds}, min class count {min_class_count}).")

        # Stratification Loop
        try:
            kfold = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=self.random_state)
            fold_splits = list(kfold.split(X, y_label))
        except ValueError:
            kfold = KFold(n_splits=n_splits, shuffle=True, random_state=self.random_state)
            fold_splits = list(kfold.split(X))

        oof_preds = np.zeros(len(X), dtype=np.int64)
        oof_probs = np.zeros((len(X), num_classes_label), dtype=np.float32)
        self.cv_accuracies, self.cv_top3_accuracies = [], []
        n_folds = len(fold_splits)
        fold_span = 0.50
        fold_base = 0.34

        for fold_idx, (train_idx, val_idx) in enumerate(fold_splits):
            report(
                fold_base + (fold_idx / n_folds) * fold_span,
                f"Cross-validation · fold {fold_idx + 1}/{n_folds} · training…",
            )

            X_tr, X_va = X[train_idx], X[val_idx]
            y_tr_l, y_va_l = y_label[train_idx], y_label[val_idx]

            fold_model = MaterialPredictor(
                num_features, num_classes_label, num_classes_type, num_classes_supplier, dropout
            ).to(self.device)

            y_train_dict = {"label": y_tr_l}
            y_val_dict = {"label": y_va_l}
            if self.use_multitask:
                y_train_dict.update({"type": y_type[train_idx], "supplier": y_supplier[train_idx]})
                y_val_dict.update({"type": y_type[val_idx], "supplier": y_supplier[val_idx]})

            def _fold_epoch_cb(epoch: int, total_epochs: int, val_acc: float, _fi=fold_idx):
                inner = (epoch + 1) / max(total_epochs, 1)
                frac = fold_base + ((_fi + inner) / n_folds) * fold_span
                report(
                    frac,
                    f"Fold {_fi + 1}/{n_folds} · epoch {epoch + 1}/{total_epochs} · val accuracy {val_acc:.3f}",
                )

            self._train_fold(
                fold_model,
                X_tr,
                y_train_dict,
                X_va,
                y_val_dict,
                epochs,
                lr,
                batch_size,
                patience_limit,
                num_classes_label=num_classes_label,
                epoch_callback=_fold_epoch_cb,
            )

            # Evaluate Out-Of-Fold Predictions
            fold_model.eval()
            with torch.no_grad():
                X_va_tensor = torch.from_numpy(X_va).to(self.device)
                if self.use_multitask:
                    logits_l, _, _ = fold_model(X_va_tensor)
                else:
                    logits_l = fold_model(X_va_tensor)
                
                probs_l = torch.softmax(logits_l, dim=1).cpu().numpy()
                oof_preds[val_idx] = probs_l.argmax(axis=1)
                oof_probs[val_idx] = probs_l
                
                fold_acc = accuracy_score(y_va_l, oof_preds[val_idx])
                self.cv_accuracies.append(fold_acc)
                self.cv_top3_accuracies.append(top_k_accuracy_score(y_va_l, probs_l, k=3, labels=np.arange(num_classes_label)))

            report(
                fold_base + ((fold_idx + 1) / n_folds) * fold_span,
                f"Fold {fold_idx + 1}/{n_folds} complete · accuracy {fold_acc:.3f}",
            )

        # Report Summary Metrics
        print(f"\n{'='*60}\nK-FOLD EVALUATION MATRIX (Multitask Toggle: {self.use_multitask})\n{'='*60}")
        print(f"  Mean Top-1 Accuracy: {np.mean(self.cv_accuracies):.4f} ± {np.std(self.cv_accuracies):.4f}")
        print(f"  Mean Top-3 Accuracy: {np.mean(self.cv_top3_accuracies):.4f} ± {np.std(self.cv_top3_accuracies):.4f}")
        print(f"\nDetailed Classification Post-Mortem Report:")
        print(classification_report(self.label_encoder.inverse_transform(y_label), 
                                    self.label_encoder.inverse_transform(oof_preds), zero_division=0, digits=3))

        mean_cv = float(np.mean(self.cv_accuracies)) if self.cv_accuracies else 0.0
        report(
            0.86,
            f"Cross-validation done · mean accuracy {mean_cv:.3f} · training final model on all data…",
        )

        self.model = MaterialPredictor(num_features, num_classes_label, num_classes_type, num_classes_supplier, dropout).to(self.device)

        def _final_epoch_cb(epoch: int, total_epochs: int):
            inner = (epoch + 1) / max(total_epochs, 1)
            report(0.86 + 0.10 * inner, f"Final model · epoch {epoch + 1}/{total_epochs}")

        self._train_final(
            self.model,
            X,
            {"label": y_label, "type": y_type, "supplier": y_supplier} if self.use_multitask else {"label": y_label},
            epochs,
            lr,
            batch_size,
            epoch_callback=_final_epoch_cb,
            aux_weight=self.multitask_aux_weight,
        )
        report(0.97, "Final model weights updated.")

    def _train_fold(
        self,
        model,
        X_train,
        y_train_dict,
        X_val,
        y_val_dict,
        epochs,
        lr,
        batch_size,
        patience_limit,
        num_classes_label: int,
        epoch_callback: Callable[[int, int, float], None] | None = None,
        aux_weight: float | None = None,
    ):
        aux_weight = self.multitask_aux_weight if aux_weight is None else aux_weight
        optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)

        weights = balanced_class_weights(y_train_dict["label"], num_classes_label)
        weights_tensor = torch.FloatTensor(weights).to(self.device)

        criterion_label = nn.CrossEntropyLoss(weight=weights_tensor, label_smoothing=0.05)
        criterion_aux = nn.CrossEntropyLoss(label_smoothing=0.05)

        if self.use_multitask:
            ds = TensorDataset(
                torch.from_numpy(X_train), torch.from_numpy(y_train_dict["label"]).long(),
                torch.from_numpy(y_train_dict["type"]).long(), torch.from_numpy(y_train_dict["supplier"]).long()
            )
        else:
            ds = TensorDataset(torch.from_numpy(X_train), torch.from_numpy(y_train_dict["label"]).long())
            
        dl = DataLoader(ds, batch_size=batch_size, shuffle=True)

        best_acc, patience_counter = 0, 0
        best_state = None

        for epoch in range(epochs):
            model.train()
            for batch in dl:
                optimizer.zero_grad()
                xb = batch[0].to(self.device)
                
                if self.use_multitask:
                    logits_l, logits_t, logits_s = model(xb)
                    loss = criterion_label(logits_l, batch[1].to(self.device)) + \
                           aux_weight * criterion_aux(logits_t, batch[2].to(self.device)) + \
                           aux_weight * criterion_aux(logits_s, batch[3].to(self.device))
                else:
                    loss = criterion_label(model(xb), batch[1].to(self.device))

                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                optimizer.step()

            # Dynamic Early Stopping Verification step
            model.eval()
            with torch.no_grad():
                X_va_t = torch.from_numpy(X_val).to(self.device)
                logits = model(X_va_t)[0] if self.use_multitask else model(X_va_t)
                acc = accuracy_score(y_val_dict["label"], logits.argmax(dim=1).cpu().numpy())

            if acc > best_acc:
                best_acc = acc
                best_state = {k: v.clone() for k, v in model.state_dict().items()}
                patience_counter = 0
            else:
                patience_counter += 1

            if epoch_callback is not None:
                epoch_callback(epoch, epochs, float(acc))

            if patience_counter >= patience_limit:
                break

        if best_state is not None:
            model.load_state_dict(best_state)

    def _train_final(
        self,
        model,
        X,
        y_dict,
        epochs,
        lr,
        batch_size,
        epoch_callback: Callable[[int, int], None] | None = None,
        aux_weight: float | None = None,
    ):
        aux_weight = self.multitask_aux_weight if aux_weight is None else aux_weight
        optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
        criterion = nn.CrossEntropyLoss(label_smoothing=0.05)

        if self.use_multitask:
            ds = TensorDataset(
                torch.from_numpy(X), torch.from_numpy(y_dict["label"]).long(),
                torch.from_numpy(y_dict["type"]).long(), torch.from_numpy(y_dict["supplier"]).long()
            )
        else:
            ds = TensorDataset(torch.from_numpy(X), torch.from_numpy(y_dict["label"]).long())
            
        dl = DataLoader(ds, batch_size=batch_size, shuffle=True)

        for epoch in range(epochs):
            model.train()
            for batch in dl:
                optimizer.zero_grad()
                xb = batch[0].to(self.device)
                if self.use_multitask:
                    out_l, out_t, out_s = model(xb)
                    loss = criterion(out_l, batch[1].to(self.device)) + \
                           aux_weight * criterion(out_t, batch[2].to(self.device)) + \
                           aux_weight * criterion(out_s, batch[3].to(self.device))
                else:
                    loss = criterion(model(xb), batch[1].to(self.device))
                loss.backward()
                optimizer.step()

            if epoch_callback is not None:
                epoch_callback(epoch, epochs)

    def predict(self, df: pd.DataFrame) -> pd.DataFrame:
        """Run predictions with argmax labels and softmax confidence scores."""
        from config.settings import (
            COL_BRAND_CONFIDENCE,
            COL_SUPPLIER_CONFIDENCE,
            COL_TYPE_CONFIDENCE,
        )
        from services.brand_labels import normalize_predicted_brand

        results = df.copy()
        work = df.copy()
        col = self.column_config
        col.validate(work, require_targets=False)

        # Normalize ML inputs on a working copy only — keep export columns unchanged.
        work[col.product_description] = work[col.product_description].apply(fix_scientific_notation)
        work[col.saler] = work[col.saler].fillna("UNKNOWN")
        work[col.country_origin] = work[col.country_origin].fillna("UNKNOWN")
        work[col.hs_code] = work[col.hs_code].astype(str).str.zfill(8)

        X = self.feature_transformer.transform(work)
        self.model.eval()

        def _max_softmax_confidence(logits: torch.Tensor) -> np.ndarray:
            probs = F.softmax(logits, dim=1)
            return probs.max(dim=1).values.cpu().numpy()

        with torch.no_grad():
            X_tensor = torch.from_numpy(X).to(self.device)
            if self.use_multitask:
                logits_l, logits_t, logits_s = self.model(X_tensor)
                pred_l = logits_l.argmax(dim=1).cpu().numpy()
                pred_t = logits_t.argmax(dim=1).cpu().numpy()
                pred_s = logits_s.argmax(dim=1).cpu().numpy()
                brand_conf = _max_softmax_confidence(logits_l)
                type_conf = _max_softmax_confidence(logits_t)
                supplier_conf = _max_softmax_confidence(logits_s)
            else:
                logits_l = self.model(X_tensor)
                pred_l = logits_l.argmax(dim=1).cpu().numpy()
                brand_conf = _max_softmax_confidence(logits_l)
                type_conf = None
                supplier_conf = None

        brand_vals = np.array(
            [normalize_predicted_brand(v) for v in self.label_encoder.inverse_transform(pred_l)],
            dtype=object,
        )
        if col.label not in results.columns:
            results[col.label] = brand_vals
        else:
            mask = results[col.label].isna() | (
                results[col.label].astype(str).str.strip().isin(["", "nan", "NaN", "None"])
            )
            results.loc[mask, col.label] = brand_vals[mask.values]

        results[COL_BRAND_CONFIDENCE] = np.round(brand_conf, 4)

        if self.use_multitask:
            type_vals = self.type_encoder.inverse_transform(pred_t)
            sup_vals = self.supplier_encoder.inverse_transform(pred_s)
            if col.type_col not in results.columns:
                results[col.type_col] = type_vals
            else:
                mask = results[col.type_col].isna() | (
                    results[col.type_col].astype(str).str.strip().isin(["", "nan", "NaN", "None"])
                )
                results.loc[mask, col.type_col] = type_vals[mask.values]
            if col.supplier_col not in results.columns:
                results[col.supplier_col] = sup_vals
            else:
                mask = results[col.supplier_col].isna() | (
                    results[col.supplier_col].astype(str).str.strip().isin(["", "nan", "NaN", "None"])
                )
                results.loc[mask, col.supplier_col] = sup_vals[mask.values]
            results[COL_TYPE_CONFIDENCE] = np.round(type_conf, 4)
            results[COL_SUPPLIER_CONFIDENCE] = np.round(supplier_conf, 4)

        return results

    def save(self, directory: str = "material_predictor"):
        os.makedirs(directory, exist_ok=True)
        torch.save(self.model.state_dict(), os.path.join(directory, "model.pt"))
        
        # 2. CHUYỂN ĐỔI COLUMN CONFIG THÀNH DICTIONARY THƯỜNG TRƯỚC KHI LƯU
        config_dict = {
            "hs_code": self.column_config.hs_code,
            "product_description": self.column_config.product_description,
            "saler": self.column_config.saler,
            "country_origin": self.column_config.country_origin,
            "label": self.column_config.label,
            "type_col": self.column_config.type_col,
            "supplier_col": self.column_config.supplier_col
        }
        joblib.dump({
            "feature_transformer": self.feature_transformer,
            "label_encoder": self.label_encoder,
            "type_encoder": self.type_encoder if self.use_multitask else None,
            "supplier_encoder": self.supplier_encoder if self.use_multitask else None,
            "word_tfidf_max": self.word_tfidf_max,
            "char_tfidf_max": self.char_tfidf_max,
            "use_multitask": self.use_multitask,
            "n_folds": self.n_folds,
            #"column_config": self.column_config
            "column_config_dict": config_dict  # <--- Thay đổi: Lưu dict thay vì lưu nguyên Object!
        }, os.path.join(directory, "pipeline_artifacts.joblib"))
        
    @classmethod
    def load(cls, directory: str = "material_predictor", device=None):
        """Tải mô hình đã đóng gói từ ổ đĩa lên để sẵn sàng dự đoán (Inference)."""
        device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # 1. Đọc file joblib chứa các bộ mã hóa dữ liệu
        artifacts_path = os.path.join(directory, "pipeline_artifacts.joblib")
        if not os.path.exists(artifacts_path):
            raise FileNotFoundError(f"Không tìm thấy file cấu hình tại: {artifacts_path}")

        from services.ml_compat import register_legacy_ml_module_aliases

        register_legacy_ml_module_aliases()
        artifacts = joblib.load(artifacts_path)

        # 2. Khôi phục lại đối tượng ColumnConfig từ Dictionary đã lưu
        stored_dict = dict(artifacts["column_config_dict"])
        from config.settings import COL_BRAND_NAME, COL_SUPPLIER, COL_TYPE

        legacy_map = {"label": COL_BRAND_NAME, "type": COL_TYPE, "supplier": COL_SUPPLIER}
        for key in ("label", "type_col", "supplier_col"):
            val = stored_dict.get(key)
            if val in legacy_map:
                stored_dict[key] = legacy_map[val]
        reconstructed_config = ColumnConfig(
            hs_code=stored_dict["hs_code"],
            product_description=stored_dict["product_description"],
            saler=stored_dict["saler"],
            country_origin=stored_dict["country_origin"],
            label=stored_dict["label"],
            type_col=stored_dict["type_col"],
            supplier_col=stored_dict["supplier_col"]
        )

        # 3. Khởi tạo lại class Pipeline với các thông số cũ
        pipeline = cls(
            column_config=reconstructed_config,
            word_tfidf_max=artifacts["word_tfidf_max"],
            char_tfidf_max=artifacts["char_tfidf_max"],
            n_folds=artifacts["n_folds"],
            use_multitask=artifacts["use_multitask"],
            device=device,
        )
        
        # Gán lại các bộ biến đổi đã được fit từ trước
        pipeline.feature_transformer = artifacts["feature_transformer"]
        pipeline.label_encoder = artifacts["label_encoder"]
        pipeline.type_encoder = artifacts["type_encoder"]
        pipeline.supplier_encoder = artifacts["supplier_encoder"]

        # 4. Xác định số lượng đặc trưng và số nhóm nhãn để dựng lại mạng nơ-ron
        num_features = pipeline.feature_transformer.num_features
        num_classes_label = len(pipeline.label_encoder.classes_)
        num_classes_type = len(pipeline.type_encoder.classes_) if pipeline.use_multitask else None
        num_classes_supplier = len(pipeline.supplier_encoder.classes_) if pipeline.use_multitask else None

        # 5. Khởi tạo khung mạng nơ-ron và nạp trọng số mạng từ file model.pt
        pipeline.model = MaterialPredictor(
            num_features=num_features,
            num_classes_label=num_classes_label,
            num_classes_type=num_classes_type,
            num_classes_supplier=num_classes_supplier
        ).to(device)
        
        model_path = os.path.join(directory, "model.pt")
        pipeline.model.load_state_dict(torch.load(model_path, map_location=device))
        pipeline.model.eval()  # Chuyển mô hình sang trạng thái đánh giá/dự đoán

        print(f"\n[Tải thành công] Khôi phục hoàn tất mô hình từ '{directory}/'")
        print(f"  -> Tổng số đặc trưng đầu vào: {num_features}")
        print(f"  -> Chế độ Multi-Task: {pipeline.use_multitask}")
        
        return pipeline

