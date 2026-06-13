"""Shared utilities for ETL and analytics."""
from __future__ import annotations

import re

import pandas as pd


def generate_customer_registry(input_df: pd.DataFrame) -> pd.DataFrame:
    """Unique customers with earliest year (`year_start`) per `customer_id`."""
    first_year_df = input_df.groupby("customer_id")["year"].min().reset_index()
    first_year_df.columns = ["customer_id", "year_start"]
    unique_customers = input_df[["customer_id", "customer_name"]].drop_duplicates(subset=["customer_id"])
    customer_registry = unique_customers.merge(first_year_df, on="customer_id", how="left")
    return customer_registry.sort_values(by="customer_name").reset_index(drop=True)


def clean_customs_description(text, words_to_remove=None) -> str:
    """Preprocessor for customs declaration text (CAS-safe, blacklist words)."""
    if pd.isna(text):
        return ""

    text = str(text).lower()
    text = re.sub(r"\S+#&", " ", text)
    text = re.sub(r"\b\d{1,2}[/.-]\d{1,2}[/.-]\d{4}\b", " ", text)
    text = re.sub(r"\b(\d{2,7})-(\d{2})-(\d)\b", r"\1_\2_\3", text)

    if words_to_remove:
        for word in words_to_remove:
            clean_word = str(word).strip().lower()
            if clean_word:
                pattern = r"\b" + re.escape(clean_word) + r"\b"
                text = re.sub(pattern, " ", text)

    text = re.sub(r"\b\d+(?:\.\d+)?\s*%", " ", text)
    text = re.sub(r"\b\d+(?:\.\d+)?\s*kg\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"[-.,]", " ", text)
    text = text.replace("*", " ")
    text = re.sub(
        r"[^a-zA-Z0-9_ áàảãạăắằẳẵặâấầẩẫậéèẻẽẹêếềểễệíìỉĩịóòỏõọôốồổỗộơớờởỡợúùủũụưứừửữựýỳỷỹỵđ\s/]",
        " ",
        text,
    )
    text = re.sub(r"\b\w\b", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def load_words_to_remove(file_path: str) -> list[str]:
    """Load a one-column CSV of words/phrases to strip from descriptions."""
    try:
        df = pd.read_csv(file_path, header=None)
        raw_words = df.iloc[:, 0].dropna().astype(str).tolist()
        cleaned_words = [w.strip().lower() for w in raw_words if w.strip()]
        cleaned_words.sort(key=len, reverse=True)
        return cleaned_words
    except Exception as e:
        print(f"Error loading words to remove from {file_path}: {e}")
        return []
