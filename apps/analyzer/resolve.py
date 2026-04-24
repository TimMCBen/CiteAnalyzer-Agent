from __future__ import annotations

import re

from packages.shared.models import TargetPaper

DOI_PATTERN = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)
ARXIV_PATTERN = re.compile(
    r"(?:https?://arxiv\.org/(?:abs|pdf)/)?(?P<identifier>\d{4}\.\d{4,5})(?:v\d+)?(?:\.pdf)?$",
    re.IGNORECASE,
)


def resolve_target_paper(paper_input: str) -> TargetPaper:
    normalized_input = paper_input.strip()
    doi = extract_doi(normalized_input)
    paper_id = extract_paper_id(normalized_input)
    arxiv_id = extract_arxiv_id(normalized_input)

    if doi:
        return canonicalize_target_paper(
            TargetPaper(
            canonical_id=f"doi:{doi}",
            title=None,
            doi=doi,
            source_ids={"doi": doi},
            input_type="doi",
            resolve_status="resolved",
            )
        )

    if paper_id:
        source_name, source_value = paper_id
        return canonicalize_target_paper(
            TargetPaper(
                canonical_id=f"{source_name}:{source_value}",
                title=None,
                doi=None,
                source_ids={source_name: source_value},
                input_type="paper_id",
                resolve_status="resolved",
            )
        )

    if arxiv_id:
        return canonicalize_target_paper(
            TargetPaper(
                canonical_id=f"arxiv:{arxiv_id}",
                title=None,
                doi=None,
                source_ids={"arxiv": arxiv_id},
                input_type="arxiv",
                resolve_status="resolved",
            )
        )

    if normalized_input:
        return canonicalize_target_paper(
            TargetPaper(
                canonical_id=None,
                title=normalized_input,
                doi=None,
                source_ids={},
                input_type="title",
                resolve_status="unresolved",
            )
        )

    return canonicalize_target_paper(
        TargetPaper(
            canonical_id=None,
            title=None,
            doi=None,
            input_type="unknown",
            resolve_status="unresolved",
        )
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


def extract_arxiv_id(raw_value: str) -> str | None:
    match = ARXIV_PATTERN.search(raw_value.strip())
    if not match:
        return None

    return match.group("identifier")


def canonicalize_target_paper(target_paper: TargetPaper) -> TargetPaper:
    target_paper.title = normalize_optional_text(target_paper.title)
    target_paper.doi = normalize_optional_text(target_paper.doi)
    target_paper.source_ids = {
        key: value.strip()
        for key, value in target_paper.source_ids.items()
        if value and value.strip()
    }
    target_paper.authors = [author.strip() for author in target_paper.authors if author.strip()]

    if not target_paper.canonical_id:
        if target_paper.doi:
            target_paper.canonical_id = f"doi:{target_paper.doi}"
        elif "arxiv" in target_paper.source_ids:
            target_paper.canonical_id = f"arxiv:{target_paper.source_ids['arxiv']}"

    return target_paper


def normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None

    normalized_value = value.strip()
    return normalized_value or None
