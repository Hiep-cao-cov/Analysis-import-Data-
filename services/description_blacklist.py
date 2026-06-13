"""Central description blacklist matching (ETL + Predict)."""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

import pandas as pd

from config.settings import (
    DESCRIPTION_BLACKLIST_EXTRA_BY_PRODUCT,
    DESCRIPTION_BLACKLIST_FORCE_WORD_BOUNDARY,
    DESCRIPTION_BLACKLIST_SHORT_TERM_MAX_LEN,
    DESCRIPTION_BLACKLIST_TERMS,
)


def normalize_description_text(text) -> str:
    text = unicodedata.normalize("NFC", str(text).strip().lower())
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def resolve_product_line_key(product_line: str | None) -> str | None:
    pl = (product_line or "").strip().upper()
    if pl in ("PMDI", "MDI", "TDI"):
        return pl
    return None


def get_description_blacklist_terms(*, product_line: str | None = None) -> list[str]:
    """
    Return blacklist phrases for the given product line.

    Edit terms in config/settings.py → DESCRIPTION_BLACKLIST_TERMS and
    DESCRIPTION_BLACKLIST_EXTRA_BY_PRODUCT.
    """
    terms: list[str] = list(DESCRIPTION_BLACKLIST_TERMS)
    pl = resolve_product_line_key(product_line)
    if pl:
        terms.extend(DESCRIPTION_BLACKLIST_EXTRA_BY_PRODUCT.get(pl, []))
    deduped: list[str] = []
    seen: set[str] = set()
    for raw in terms:
        text = str(raw).strip()
        if not text:
            continue
        key = normalize_description_text(text)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(text)
    return deduped


def uses_word_boundary(term: str) -> bool:
    normalized = normalize_description_text(term)
    if not normalized:
        return False
    if normalized in DESCRIPTION_BLACKLIST_FORCE_WORD_BOUNDARY:
        return True
    return len(normalized) <= DESCRIPTION_BLACKLIST_SHORT_TERM_MAX_LEN


@lru_cache(maxsize=512)
def _compiled_pattern(normalized_term: str, word_boundary: bool) -> re.Pattern[str]:
    escaped = re.escape(normalized_term)
    if word_boundary:
        body = rf"(?<!\w){escaped}(?!\w)"
    else:
        body = escaped
    return re.compile(body, flags=re.IGNORECASE | re.UNICODE)


def find_description_blacklist_match(
    description,
    terms: list[str] | None = None,
    *,
    product_line: str | None = None,
) -> str | None:
    """Return the first matching blacklist term, or None."""
    term_list = terms if terms is not None else get_description_blacklist_terms(product_line=product_line)
    norm_desc = normalize_description_text(description)
    if not norm_desc:
        return None
    for raw_term in term_list:
        norm_term = normalize_description_text(raw_term)
        if not norm_term:
            continue
        pattern = _compiled_pattern(norm_term, uses_word_boundary(raw_term))
        if pattern.search(norm_desc):
            return raw_term
    return None


def description_is_blacklisted(
    description,
    terms: list[str] | None = None,
    *,
    product_line: str | None = None,
) -> bool:
    return find_description_blacklist_match(description, terms, product_line=product_line) is not None


def mask_blacklisted_descriptions(
    descriptions: pd.Series,
    terms: list[str] | None = None,
    *,
    product_line: str | None = None,
) -> pd.Series:
    term_list = terms if terms is not None else get_description_blacklist_terms(product_line=product_line)
    return descriptions.map(lambda val: description_is_blacklisted(val, term_list, product_line=product_line))


def blacklist_delete_reason(matched_term: str, *, product_line: str | None = None) -> str:
    pl = resolve_product_line_key(product_line) or "ALL"
    mode = "word boundary" if uses_word_boundary(matched_term) else "phrase"
    return (
        f"delete_description: description matches blacklist term '{matched_term}' "
        f"(settings.py · product={pl} · match={mode})"
    )
