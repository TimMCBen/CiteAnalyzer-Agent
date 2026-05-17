"""Command-line validation helpers for runtime logging contract."""
from __future__ import annotations

import io
import ssl
import sys
from contextlib import redirect_stdout
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from apps.analyzer.nodes import (
    analyze_author_intel_node,
    analyze_citation_sentiments_node,
    fetch_fulltext_documents_node,
    generate_report_node,
)
from packages.author_intel.service import analyze_author_intel
from packages.citation_sources.clients.semantic_scholar import (
    DEFAULT_CITATION_FIELDS,
    DEFAULT_RESOLVE_FIELDS,
    SemanticScholarClient,
)
from packages.citation_sources.models import CitingPaper
from packages.citation_sources.service import attach_fetch_result_to_state, fetch_citation_candidates
from packages.sentiment.models import ReferenceMatch, TextSourceSelection
from packages.sentiment.workflow import run_stage6_workflow
from packages.shared.models import AnalysisState, TargetPaper
from packages.shared.runtime_logging import RuntimeLogger, runtime_context
from scripts.test_agent.stage_logging import StageLogger


class FakeSemanticScholarNoCitations:
    """Test double that simulates fake Semantic Scholar no citations behavior."""
    def resolve_target_paper(self, target_paper: TargetPaper) -> dict[str, object]:
        """Resolve target paper for fake Semantic Scholar no citations."""
        return {"paper_id": target_paper.canonical_id or "fixture:no-citations"}

    def fetch_citations(self, paper_ref: dict[str, object], max_results: int = 20) -> list[dict[str, object]]:
        """Fetch citations for fake Semantic Scholar no citations."""
        return []


class FakeCrossrefClient:
    """Client wrapper for fake Crossref operations used by stage validation."""
    def enrich_candidate(self, candidate: dict[str, object]) -> dict[str, object]:
        """Enrich a citation candidate fixture for fake Crossref client."""
        return candidate


class FailingOpenAlexClient:
    """Client wrapper for failing open alex operations used by stage validation."""
    def lookup_author(self, name: str) -> dict[str, object] | None:
        """Look up author for failing open alex client."""
        raise ssl.SSLError("simulated TLS disconnect")


class EmptyDBLPClient:
    """Client wrapper for empty d b l p operations used by stage validation."""
    def lookup_author(self, name: str) -> dict[str, object] | None:
        """Look up author for empty d b l p client."""
        return None


def capture_detail(callable_obj) -> str:
    """Capture runtime detail events for assertions for stage validation."""
    stream = io.StringIO()
    with redirect_stdout(stream), runtime_context(logger=RuntimeLogger(mode="detail")):
        callable_obj()
    return stream.getvalue()


def assert_semantic_scholar_field_and_arxiv_contract() -> None:
    assert "authors.name" not in DEFAULT_RESOLVE_FIELDS, DEFAULT_RESOLVE_FIELDS
    assert "citingPaper.authors.name" not in DEFAULT_CITATION_FIELDS, DEFAULT_CITATION_FIELDS
    assert "authors" in DEFAULT_RESOLVE_FIELDS, DEFAULT_RESOLVE_FIELDS
    assert "citingPaper.authors" in DEFAULT_CITATION_FIELDS, DEFAULT_CITATION_FIELDS

    client = SemanticScholarClient(api_key="s2k-test-redacted", backoff_seconds=0)
    target = TargetPaper(
        canonical_id="2504.19162v2",
        paper_query="https://arxiv.org/abs/2504.19162v2",
        paper_query_type="arxiv",
        title="Fixture target",
        source_ids={"arxiv": "2504.19162v2"},
        resolve_status="resolved",
    )
    identifiers = list(client._candidate_identifiers(target))  # noqa: SLF001 - contract covers boundary behavior.
    assert "ARXIV:2504.19162" in identifiers, identifiers
    assert all("v2" not in identifier for identifier in identifiers if identifier.startswith("ARXIV:")), identifiers


def assert_runtime_logger_redacts_secrets() -> None:
    output = capture_detail(
        lambda: RuntimeLogger(mode="detail").detail(
            "semantic_scholar.request",
            "脱敏测试",
            api_key="s2k-secret-value",
            authorization="Bearer hidden",
            safe="visible",
        )
    )
    assert "visible" in output, output
    assert "s2k-secret-value" not in output, output
    assert "Bearer hidden" not in output, output
    assert "[REDACTED]" in output, output


def assert_zero_citation_runtime_contract() -> None:
    def run_case() -> None:
        target = TargetPaper(
            canonical_id="fixture:no-citations",
            paper_query="fixture:no-citations",
            paper_query_type="title",
            title="No Citation Fixture",
            resolve_status="resolved",
        )
        state: AnalysisState = AnalysisState(
            raw_query="fixture no citations",
            request_type="citation_analysis",
            analysis_goal="citation_analysis",
            constraints={},
            target_paper=target,
            errors=[],
            status="target_paper_resolved",
        )
        result = fetch_citation_candidates(
            target_paper=target,
            semantic_scholar_client=FakeSemanticScholarNoCitations(),
            crossref_client=FakeCrossrefClient(),
            max_results=3,
        )
        state = attach_fetch_result_to_state(state, result)
        state = analyze_author_intel_node(state)
        state = fetch_fulltext_documents_node(state)
        state = analyze_citation_sentiments_node(state)
        state = generate_report_node(state)

        assert state["status"] == "report_generated", state["status"]
        assert state["errors"] == [], state["errors"]
        assert state["author_profiles"] == [], state["author_profiles"]
        assert state["citation_contexts"] == [], state["citation_contexts"]
        html_path = Path(state["report_artifact"].export_paths["html"])
        json_path = Path(state["report_artifact"].export_paths["json"])
        pdf_path = Path(state["report_artifact"].export_paths["pdf"])
        assert html_path.exists(), html_path
        assert json_path.exists(), json_path
        assert pdf_path.exists(), pdf_path

    output = capture_detail(run_case)
    assert "SKIP" in output, output
    assert "Semantic Scholar 当前返回 0 篇施引文献" in output, output
    assert "没有施引文献" in output, output


def assert_openalex_warning_contract() -> None:
    output = capture_detail(
        lambda: analyze_author_intel(
            citing_papers=[CitingPaper(canonical_id="citing-1", title="Paper", authors=["Lei Bai"])],
            openalex_client=FailingOpenAlexClient(),
            dblp_client=EmptyDBLPClient(),
        )
    )
    assert "WARN openalex.lookup" in output, output
    assert "Lei Bai" in output, output
    assert "impact=single_author" in output, output


def assert_grobid_logging_contract() -> None:
    import packages.sentiment.workflow as workflow

    original = workflow.locate_reference_context_from_grobid_pdf
    target = TargetPaper(
        canonical_id="target",
        paper_query="target",
        paper_query_type="title",
        title="Target Paper",
        resolve_status="resolved",
    )
    citing = CitingPaper(canonical_id="citing-1", title="Citing Paper")
    text_source = TextSourceSelection(
        citing_paper_id="citing-1",
        text="short text",
        source_type="pdf",
        source_label="fixture.pdf",
        raw_path=str(REPO_ROOT / "downloaded-papers" / "fixture.pdf"),
    )

    def hit(*args, **kwargs) -> ReferenceMatch:
        return ReferenceMatch(
            matched_target_reference="target-ref",
            context_text="short context",
            mention_span=None,
            evidence_note="matched_by_grobid_fixture",
        )

    def miss(*args, **kwargs) -> ReferenceMatch:
        return ReferenceMatch(
            matched_target_reference=None,
            context_text=None,
            mention_span=None,
            evidence_note="grobid_fixture_miss",
        )

    try:
        workflow.locate_reference_context_from_grobid_pdf = hit
        hit_output = capture_detail(lambda: run_stage6_workflow(target, citing, text_source))
        assert "GROBID 命中" in hit_output, hit_output
        assert "citing_paper_id=citing-1" in hit_output, hit_output

        workflow.locate_reference_context_from_grobid_pdf = miss
        miss_output = capture_detail(lambda: run_stage6_workflow(target, citing, text_source))
        assert "GROBID 未命中" in miss_output, miss_output
        assert "降级" in miss_output, miss_output
    finally:
        workflow.locate_reference_context_from_grobid_pdf = original


def main() -> None:
    """Run this module as a command-line validation or utility entry point."""
    logger = StageLogger("runtime_logging")
    logger.start()
    assert_semantic_scholar_field_and_arxiv_contract()
    logger.pass_case("semantic_scholar_fields_and_arxiv_normalization")
    assert_runtime_logger_redacts_secrets()
    logger.pass_case("runtime_logger_redacts_secrets")
    assert_zero_citation_runtime_contract()
    logger.pass_case("zero_citation_generates_report")
    assert_openalex_warning_contract()
    logger.pass_case("openalex_single_author_warning")
    assert_grobid_logging_contract()
    logger.pass_case("grobid_hit_and_miss_logging")
    logger.done("runtime logging contract passed")


if __name__ == "__main__":
    main()
