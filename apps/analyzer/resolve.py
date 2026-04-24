from __future__ import annotations

import re

from packages.shared.models import TargetPaper

DOI_PATTERN = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)


def resolve_target_paper(paper_input: str) -> TargetPaper:
    normalized_input = paper_input.strip()
    doi = extract_doi(normalized_input)

    if doi:
        return TargetPaper(
            canonical_id=f"doi:{doi}",
            title=None,
            doi=doi,
            source_ids={"doi": doi},
            input_type="doi",
            resolve_status="resolved",
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
