from __future__ import annotations

from typing import Any, Protocol

from packages.citation_sources.dedupe import merge_normalized_records
from packages.citation_sources.models import CitationFetchResult, FetchSummary
from packages.citation_sources.normalize import normalize_source_record
from packages.shared.models import AnalysisState, TargetPaper


class SemanticScholarClientProtocol(Protocol):
    def resolve_target_paper(self, target_paper: TargetPaper) -> dict[str, object]:
        ...

    def fetch_citations(self, paper_ref: dict[str, object], max_results: int = 20) -> list[dict[str, object]]:
        ...


class CrossrefClientProtocol(Protocol):
    def enrich_candidate(self, candidate: dict[str, object]) -> dict[str, object]:
        ...


def fetch_citation_candidates(
    target_paper: TargetPaper,
    semantic_scholar_client: SemanticScholarClientProtocol,
    crossref_client: CrossrefClientProtocol,
    max_results: int = 20,
) -> CitationFetchResult:
    target_query = target_paper.doi or target_paper.canonical_id or target_paper.paper_query or "unknown"
    summary = FetchSummary(target_query=target_query)
    errors: list[str] = []
    normalized_records: list[dict[str, object]] = []
    crossref_error_recorded = False

    try:
        paper_ref = semantic_scholar_client.resolve_target_paper(target_paper)
        raw_records = semantic_scholar_client.fetch_citations(paper_ref, max_results=max_results)
        summary.semantic_scholar_candidates = len(raw_records)
    except Exception as exc:
        errors.append(f"semantic_scholar: {exc}")
        summary.partial_failure = True
        summary.notes.append(f"semantic_scholar failed: {exc}")
        raw_records = []

    for record in raw_records:
        working_record = dict(record)
        try:
            enriched_record = crossref_client.enrich_candidate(working_record)
        except Exception as exc:
            summary.partial_failure = True
            if not crossref_error_recorded:
                summary.notes.append(f"crossref failed: {exc}")
                errors.append(f"crossref: {exc}")
                crossref_error_recorded = True
            enriched_record = working_record
        else:
            if enriched_record.get("source_name") == "crossref":
                summary.crossref_candidates += 1
            elif "crossref" in [str(name) for name in enriched_record.get("source_names", [])]:
                summary.crossref_candidates += 1

        normalized_records.append(normalize_source_record(record=enriched_record, query_used=target_query))

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


def fetch_citation_candidates_with_live_clients(
    target_paper: TargetPaper,
    max_results: int = 20,
) -> CitationFetchResult:
    from packages.citation_sources.clients import CrossrefClient, SemanticScholarClient

    return fetch_citation_candidates(
        target_paper=target_paper,
        semantic_scholar_client=SemanticScholarClient(),
        crossref_client=CrossrefClient(),
        max_results=max_results,
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
