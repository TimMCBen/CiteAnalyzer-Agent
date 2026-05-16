from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.citation_sources.service import fetch_citation_candidates
from packages.citation_sources.clients import CrossrefClient, SemanticScholarClient
from packages.shared.models import TargetPaper
from scripts.test_agent.stage_logging import StageLogger


class FakeSemanticScholarClient:
    def resolve_target_paper(self, target_paper: TargetPaper):
        return {
            "paper_id": "S2-TARGET-1",
            "title": target_paper.title,
            "doi": target_paper.doi,
        }

    def fetch_citations(self, target_paper: TargetPaper, max_results: int = 20):
        return [
            {
                "source_name": "semantic_scholar",
                "source_record_id": "S2-1",
                "title": "Citation Graphs for Transformers",
                "doi": "10.1000/alpha",
                "year": 2021,
                "authors": ["Alice Smith", "Bob Lee"],
                "venue": "ACL",
                "abstract": "Semantic Scholar result",
                "url": "https://example.org/semantic/alpha",
            },
            {
                "source_name": "semantic_scholar",
                "source_record_id": "S2-2",
                "title": "Evaluating Citation Pipelines",
                "doi": None,
                "year": 2022,
                "authors": ["Carol Ng"],
                "venue": "EMNLP",
                "abstract": None,
                "url": "https://example.org/semantic/beta",
            },
        ]


class FakeCrossrefClient:
    def enrich_candidate(self, candidate: dict[str, object]):
        source_names = list(candidate.get("source_names") or [])
        if candidate.get("source_record_id") == "S2-1":
            source_names.append("crossref")
            candidate["source_names"] = source_names
            candidate["source_specific_ids"] = {"semantic_scholar": "S2-1", "crossref": "CR-1"}
            candidate["source_links"] = {
                "semantic_scholar": "https://example.org/semantic/alpha",
                "crossref": "https://example.org/crossref/alpha",
            }
            candidate["venue"] = "ACL 2021"
            return candidate

        if candidate.get("source_record_id") == "S2-2":
            source_names.append("crossref")
            candidate["source_names"] = source_names
            candidate["source_specific_ids"] = {"semantic_scholar": "S2-2", "crossref": "CR-2"}
            candidate["doi"] = "10.1000/beta"
            candidate["source_links"] = {
                "semantic_scholar": "https://example.org/semantic/beta",
                "crossref": "https://example.org/crossref/beta",
            }
            return candidate

        return candidate


class FailingCrossrefClient:
    def enrich_candidate(self, candidate: dict[str, object]):
        raise RuntimeError("crossref unavailable")


def build_target_paper() -> TargetPaper:
    return TargetPaper(
        canonical_id="paper-1",
        paper_query="10.1145/3368089.3409740",
        paper_query_type="doi",
        title="Sample Target Paper",
        doi="10.1145/3368089.3409740",
        source_ids={"doi": "10.1145/3368089.3409740"},
        resolve_status="resolved",
    )


def assert_merge_across_sources():
    result = fetch_citation_candidates(
        target_paper=build_target_paper(),
        semantic_scholar_client=FakeSemanticScholarClient(),
        crossref_client=FakeCrossrefClient(),
        max_results=10,
    )

    assert len(result.citing_papers) == 2, f"expected 2 deduped papers, got {len(result.citing_papers)}"
    assert result.fetch_summary.semantic_scholar_candidates == 2
    assert result.fetch_summary.crossref_candidates == 2
    assert result.fetch_summary.merged_candidates == 2
    assert result.fetch_summary.deduped_candidates == 2
    assert result.fetch_summary.partial_failure is False
    assert result.fetch_summary.target_title == "Sample Target Paper"
    assert result.fetch_summary.target_doi == "10.1145/3368089.3409740"
    assert result.fetch_summary.target_resolve_status == "resolved"

    merged = next(paper for paper in result.citing_papers if paper.doi == "10.1000/alpha")
    assert merged.source_names == ["crossref", "semantic_scholar"], f"unexpected source names: {merged.source_names}"
    enriched = next(paper for paper in result.citing_papers if paper.doi == "10.1000/beta")
    assert enriched.source_names == ["crossref", "semantic_scholar"], f"unexpected source names: {enriched.source_names}"
    assert len(result.source_trace) == 2, f"expected 2 source traces, got {len(result.source_trace)}"
    return result


def assert_partial_failure():
    result = fetch_citation_candidates(
        target_paper=build_target_paper(),
        semantic_scholar_client=FakeSemanticScholarClient(),
        crossref_client=FailingCrossrefClient(),
        max_results=10,
    )

    assert len(result.citing_papers) == 2, f"expected 2 papers on partial failure, got {len(result.citing_papers)}"
    assert result.fetch_summary.partial_failure is True
    assert any("crossref" in note.lower() for note in result.fetch_summary.notes), result.fetch_summary.notes
    assert result.errors == ["crossref: crossref unavailable"], f"unexpected errors: {result.errors}"
    return result


def assert_missing_title_rejected() -> None:
    target_paper = TargetPaper(
        canonical_id="paper-1",
        paper_query="10.1145/3368089.3409740",
        paper_query_type="doi",
        title=None,
        doi="10.1145/3368089.3409740",
        source_ids={"doi": "10.1145/3368089.3409740"},
        resolve_status="resolved",
    )
    try:
        fetch_citation_candidates(
            target_paper=target_paper,
            semantic_scholar_client=FakeSemanticScholarClient(),
            crossref_client=FakeCrossrefClient(),
            max_results=10,
        )
    except ValueError as exc:
        assert "target_paper.title" in str(exc), exc
        return
    raise AssertionError("expected stage2 to reject target paper without title")


def main() -> None:
    logger = StageLogger("stage2")
    logger.start()
    merge_result = assert_merge_across_sources()
    logger.pass_case(
        "merge_across_sources",
        detail=stage2_result_detail(merge_result, live_enabled=False),
    )
    partial_result = assert_partial_failure()
    logger.pass_case(
        "partial_failure",
        detail=stage2_result_detail(partial_result, live_enabled=False),
    )
    assert_missing_title_rejected()
    logger.pass_case("missing_title_rejected", detail="raised=ValueError field=target_paper.title")
    maybe_run_live_smoke(logger)
    logger.done("stage2 validation passed")


def stage2_result_detail(result, live_enabled: bool) -> str:
    summary = result.fetch_summary
    return (
        f"live_enabled={live_enabled} target={summary.target_doi or summary.target_title} "
        f"semantic_scholar={summary.semantic_scholar_candidates} crossref={summary.crossref_candidates} "
        f"merged={summary.merged_candidates} deduped={summary.deduped_candidates} "
        f"partial_failure={summary.partial_failure} errors={len(result.errors)}"
    )


def maybe_run_live_smoke(logger: StageLogger) -> None:
    os = __import__("os")
    live_mode = str(os.getenv("STAGE2_LIVE", "")).strip().lower()
    if live_mode not in {"1", "true", "yes"}:
        logger.detail("live_enabled=False env=STAGE2_LIVE")
        return

    target_doi = str(os.getenv("STAGE2_TARGET_DOI", "")).strip()
    if not target_doi:
        raise AssertionError("STAGE2_TARGET_DOI is required when STAGE2_LIVE is enabled")

    result = fetch_citation_candidates(
        target_paper=TargetPaper(
            canonical_id=None,
            paper_query=target_doi,
            paper_query_type="doi",
            title="Towards automated verification of smart contract fairness",
            doi=target_doi,
            source_ids={"doi": target_doi},
            resolve_status="resolved",
        ),
        semantic_scholar_client=SemanticScholarClient(),
        crossref_client=CrossrefClient(),
        max_results=5,
    )

    assert (
        result.fetch_summary.semantic_scholar_candidates > 0 or result.fetch_summary.deduped_candidates > 0
    ), f"live smoke returned no citation candidates: errors={result.errors!r}"
    logger.pass_case("live_smoke", detail=stage2_result_detail(result, live_enabled=True))


if __name__ == "__main__":
    main()
