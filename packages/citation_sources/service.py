from __future__ import annotations

from typing import Any, Protocol

from packages.citation_sources.dedupe import merge_normalized_records
from packages.citation_sources.models import CitationFetchResult, FetchSummary
from packages.citation_sources.normalize import normalize_source_record
from packages.shared.models import AnalysisState, TargetPaper


class CitationSourceClient(Protocol):
    def fetch_citations(self, target_paper: TargetPaper, max_results: int = 20) -> list[dict[str, object]]:
        ...


def fetch_citation_candidates(
    target_paper: TargetPaper,
    semantic_scholar_client: CitationSourceClient,
    crossref_client: CitationSourceClient,
    max_results: int = 20,
) -> CitationFetchResult:
    target_query = target_paper.doi or target_paper.canonical_id or target_paper.paper_query or "unknown"
    summary = FetchSummary(target_query=target_query)
    errors: list[str] = []
    normalized_records: list[dict[str, object]] = []

    source_runs = [
        ("semantic_scholar", semantic_scholar_client),
        ("crossref", crossref_client),
    ]

    for source_name, client in source_runs:
        try:
            raw_records = client.fetch_citations(target_paper, max_results=max_results)
        except Exception as exc:
            summary.partial_failure = True
            summary.notes.append(f"{source_name} failed: {exc}")
            errors.append(f"{source_name}: {exc}")
            continue

        if source_name == "semantic_scholar":
            summary.semantic_scholar_candidates = len(raw_records)
        elif source_name == "crossref":
            summary.crossref_candidates = len(raw_records)

        normalized_records.extend(
            normalize_source_record(record=record, query_used=target_query) for record in raw_records
        )

    summary.merged_candidates = len(normalized_records)
    deduped_papers, source_trace = merge_normalized_records(normalized_records)
    summary.deduped_candidates = len(deduped_papers)

    if not deduped_papers and errors:
        summary.notes.append("no citation candidates survived source failures")

    return CitationFetchResult(
        citing_papers=deduped_papers,
        source_trace=source_trace,
        fetch_summary=summary,
        errors=errors,
    )


def attach_fetch_result_to_state(state: AnalysisState, result: CitationFetchResult) -> AnalysisState:
    state["citing_papers"] = result.citing_papers  # type: ignore[assignment]
    state["source_trace"] = result.source_trace  # type: ignore[assignment]
    state["fetch_summary"] = result.fetch_summary  # type: ignore[assignment]
    if result.errors:
        state.setdefault("errors", [])
        state["errors"].extend(result.errors)
    state["status"] = "citations_fetched"
    return state
