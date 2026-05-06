from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable

from packages.citation_sources.models import CitingPaper


NAME_SEP_PATTERN = re.compile(r"\s+")
NON_WORD_PATTERN = re.compile(r"[^a-z0-9 ]+")


@dataclass
class AuthorCandidate:
    display_name: str
    normalized_name: str
    frequency: int = 0
    source_paper_ids: list[str] = field(default_factory=list)
    affiliations_hint: list[str] = field(default_factory=list)


def normalize_author_name(name: str) -> str:
    collapsed = NAME_SEP_PATTERN.sub(" ", str(name or "").strip().casefold())
    cleaned = NON_WORD_PATTERN.sub("", collapsed)
    return NAME_SEP_PATTERN.sub(" ", cleaned).strip()


def build_author_candidates(citing_papers: Iterable[CitingPaper]) -> list[AuthorCandidate]:
    merged: dict[str, AuthorCandidate] = {}

    for paper in citing_papers:
        paper_id = paper.canonical_id or paper.doi or paper.title
        for author_name in paper.authors:
            normalized_name = normalize_author_name(author_name)
            if not normalized_name:
                continue
            candidate = merged.get(normalized_name)
            if candidate is None:
                candidate = AuthorCandidate(
                    display_name=author_name,
                    normalized_name=normalized_name,
                )
                merged[normalized_name] = candidate

            candidate.frequency += 1
            if paper_id not in candidate.source_paper_ids:
                candidate.source_paper_ids.append(paper_id)

    return sorted(merged.values(), key=lambda item: (-item.frequency, item.normalized_name))
