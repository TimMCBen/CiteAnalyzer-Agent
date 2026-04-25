from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.citation_sources.service import fetch_citation_candidates
from packages.shared.models import TargetPaper


class FakeSemanticScholarClient:
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
    def fetch_citations(self, target_paper: TargetPaper, max_results: int = 20):
        return [
            {
                "source_name": "crossref",
                "source_record_id": "CR-1",
                "title": "Citation Graphs for Transformers",
                "doi": "10.1000/alpha",
                "year": 2021,
                "authors": ["Alice Smith", "Bob Lee"],
                "venue": "ACL 2021",
                "abstract": None,
                "url": "https://example.org/crossref/alpha",
            },
            {
                "source_name": "crossref",
                "source_record_id": "CR-3",
                "title": "Crossref Metadata Backfill",
                "doi": "10.1000/gamma",
                "year": 2020,
                "authors": ["Dana Xu"],
                "venue": "Findings",
                "abstract": None,
                "url": "https://example.org/crossref/gamma",
            },
        ]


class FailingCrossrefClient:
    def fetch_citations(self, target_paper: TargetPaper, max_results: int = 20):
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


def assert_merge_across_sources() -> None:
    result = fetch_citation_candidates(
        target_paper=build_target_paper(),
        semantic_scholar_client=FakeSemanticScholarClient(),
        crossref_client=FakeCrossrefClient(),
        max_results=10,
    )

    assert len(result.citing_papers) == 3, f"expected 3 deduped papers, got {len(result.citing_papers)}"
    assert result.fetch_summary.semantic_scholar_candidates == 2
    assert result.fetch_summary.crossref_candidates == 2
    assert result.fetch_summary.merged_candidates == 4
    assert result.fetch_summary.deduped_candidates == 3
    assert result.fetch_summary.partial_failure is False

    merged = next(paper for paper in result.citing_papers if paper.doi == "10.1000/alpha")
    assert merged.source_names == ["crossref", "semantic_scholar"], f"unexpected source names: {merged.source_names}"
    assert len(result.source_trace) == 4, f"expected 4 source traces, got {len(result.source_trace)}"


def assert_partial_failure() -> None:
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


def main() -> None:
    assert_merge_across_sources()
    print("[PASS] stage2::merge_across_sources")
    assert_partial_failure()
    print("[PASS] stage2::partial_failure")
    print("stage2 validation passed")


if __name__ == "__main__":
    main()
