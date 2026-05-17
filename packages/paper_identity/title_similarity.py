"""Title similarity helpers for paper identity matching."""
from __future__ import annotations

import re
from difflib import SequenceMatcher


SPACE_PATTERN = re.compile(r"\s+")
NON_ALNUM_PATTERN = re.compile(r"[^a-z0-9]+")


def normalize_title_for_match(title: str) -> str:
    """Normalize title for match for paper identity matching."""
    text = NON_ALNUM_PATTERN.sub(" ", str(title or "").lower())
    return SPACE_PATTERN.sub(" ", text).strip()


def title_similarity(left: str, right: str) -> float:
    """Score normalized title similarity for identity matching for paper identity matching."""
    normalized_left = normalize_title_for_match(left)
    normalized_right = normalize_title_for_match(right)
    if not normalized_left or not normalized_right:
        return 0.0
    return SequenceMatcher(None, normalized_left, normalized_right).ratio()


def normalize_author_name(name: str) -> str:
    """Normalize author name for paper identity matching."""
    text = NON_ALNUM_PATTERN.sub(" ", str(name or "").casefold())
    return SPACE_PATTERN.sub(" ", text).strip()


def author_name_overlap(left: list[str], right: list[str]) -> float:
    """Measure author-name overlap between candidate records for paper identity matching."""
    left_names = {normalize_author_name(name) for name in left if normalize_author_name(name)}
    right_names = {normalize_author_name(name) for name in right if normalize_author_name(name)}
    if not left_names or not right_names:
        return 0.0
    return len(left_names & right_names) / max(len(left_names), len(right_names))
