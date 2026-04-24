from __future__ import annotations

import re

from packages.shared.models import TargetPaper

DOI_PATTERN = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)


def resolve_target_paper(paper_input: str) -> TargetPaper:
    normalized_input = paper_input.strip()
    doi = extract_doi(normalized_input)
    paper_id = extract_paper_id(normalized_input)

    if doi:
        return TargetPaper(
            canonical_id=f"doi:{doi}",
            title=None,
            doi=doi,
            source_ids={"doi": doi},
            input_type="doi",
            resolve_status="resolved",
        )

    if paper_id:
        source_name, source_value = paper_id
        return TargetPaper(
            canonical_id=f"{source_name}:{source_value}",
            title=None,
            doi=None,
            source_ids={source_name: source_value},
            input_type="paper_id",
            resolve_status="resolved",
        )

    if normalized_input:
        return TargetPaper(
            canonical_id=None,
            title=normalized_input,
            doi=None,
            source_ids={},
            input_type="title",
            resolve_status="unresolved",
        )

    return TargetPaper(
        canonical_id=None,
        title=None,
        doi=None,
        input_type="unknown",
        resolve_status="unresolved",
    )


def extract_doi(raw_value: str) -> str | None:
    match = DOI_PATTERN.search(raw_value)
    if not match:
        return None

    return match.group(0).lower()


def extract_paper_id(raw_value: str) -> tuple[str, str] | None:
    normalized_value = raw_value.strip()
    lowered_value = normalized_value.lower()

    if lowered_value.startswith("s2:"):
        return ("semantic_scholar", normalized_value[3:])

    if lowered_value.startswith("corpusid:"):
        return ("corpus_id", normalized_value[9:])

    if lowered_value.startswith("openalex:"):
        return ("openalex", normalized_value[9:])

    return None
