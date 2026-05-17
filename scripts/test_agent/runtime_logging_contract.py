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
    def resolve_target_paper(self, target_paper: TargetPaper) -> dict[str, object]:
        return {"paper_id": target_paper.canonical_id or "fixture:no-citations"}

    def fetch_citations(self, paper_ref: dict[str, object], max_results: int = 20) -> list[dict[str, object]]:
        return []


class FakeCrossrefClient:
    def enrich_candidate(self, candidate: dict[str, object]) -> dict[str, object]:
        return candidate


class FailingOpenAlexClient:
    def lookup_author(self, name: str) -> dict[str, object] | None:
        raise ssl.SSLError("simulated TLS disconnect")


class EmptyDBLPClient:
    def lookup_author(self, name: str) -> dict[str, object] | None:
        return None


class ProgressOpenAlexClient:
    def lookup_author(self, name: str) -> dict[str, object] | None:
        if name == "Failing Author":
            raise ssl.SSLError("simulated TLS disconnect")
        if name in {"Ada Lovelace", "Grace Hopper"}:
            return {
                "author_id": f"openalex:{name}",
                "name": name,
                "h_index": 40,
                "citation_count": 1000,
                "works_count": 80,
                "source_ids": {"openalex": f"openalex:{name}"},
                "evidence_sources": ["openalex"],
            }
        return None


def capture_detail(callable_obj) -> str:
    return capture_runtime(callable_obj, mode="detail")


def capture_runtime(callable_obj, mode: str) -> str:
    stream = io.StringIO()
    with redirect_stdout(stream), runtime_context(logger=RuntimeLogger(mode=mode)):
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
        assert html_path.exists(), html_path
        assert json_path.exists(), json_path

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


def run_author_progress_fixture() -> None:
    analyze_author_intel(
        citing_papers=[
            CitingPaper(
                canonical_id="citing-progress",
                title="Progress Fixture",
                authors=[
                    "Ada Lovelace",
                    "Grace Hopper",
                    "Weak Author",
                    "Failing Author",
                    "Another Weak Author",
                    "Final Weak Author",
                ],
            )
        ],
        openalex_client=ProgressOpenAlexClient(),
        dblp_client=EmptyDBLPClient(),
    )


def assert_stage4_progress_detail_contract() -> None:
    output = capture_detail(run_author_progress_fixture)
    progress_lines = [line for line in output.splitlines() if "PROGRESS 阶段4" in line]
    assert len(progress_lines) == 6, output
    assert "作者画像" in output, output
    assert "1/6" in output, output
    assert "6/6 100%" in output, output
    assert "current=Ada Lovelace" in output, output
    assert "status=matched" in output, output
    assert "status=weak_signal" in output, output
    assert "status=failed_lookup" in output, output
    assert "matched=" in output, output
    assert "weak=" in output, output
    assert "failed=" in output, output


def assert_stage4_progress_brief_contract() -> None:
    output = capture_runtime(run_author_progress_fixture, mode="brief")
    progress_lines = [line for line in output.splitlines() if "PROGRESS 阶段4" in line]
    assert 1 <= len(progress_lines) < 6, output
    assert "6/6 100%" in output, output


def assert_stage4_progress_quiet_contract() -> None:
    output = capture_runtime(run_author_progress_fixture, mode="quiet")
    assert "PROGRESS 阶段4" not in output, output


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
    assert_stage4_progress_detail_contract()
    logger.pass_case("stage4_progress_detail")
    assert_stage4_progress_brief_contract()
    logger.pass_case("stage4_progress_brief")
    assert_stage4_progress_quiet_contract()
    logger.pass_case("stage4_progress_quiet")
    assert_grobid_logging_contract()
    logger.pass_case("grobid_hit_and_miss_logging")
    logger.done("runtime logging contract passed")


if __name__ == "__main__":
    main()
