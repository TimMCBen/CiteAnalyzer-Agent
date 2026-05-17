"""Command-line validation helpers for e2e mvp."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from apps.analyzer import nodes
from apps.analyzer.main import run_analysis
from apps.analyzer.resolve import resolve_target_paper_metadata as real_resolve_target_paper_metadata
from packages.author_intel.service import analyze_author_intel
from packages.citation_sources.models import CitationFetchResult
from packages.shared.models import TargetPaper
from scripts.test_agent.stage4 import FakeDBLPClient, FakeOpenAlexClient
from scripts.test_agent.stage6 import (
    DEFAULT_SAMPLE_PATH,
    build_local_source_links,
    fake_classify_sentiment,
    fake_reference_matcher,
    load_stage2_sample,
)
from scripts.test_agent.stage_logging import StageLogger


def assert_e2e_mvp_real_sample():
    target_paper, citing_papers = load_stage2_sample(DEFAULT_SAMPLE_PATH)
    temp_dir = build_local_source_links(citing_papers, target_paper.doi or "")

    original_resolve = nodes.resolve_target_paper_metadata
    original_fetch = nodes.fetch_citation_candidates_with_live_clients
    original_author_intel = nodes.analyze_author_intel_with_live_clients
    original_sentiment = nodes.analyze_citation_sentiments

    import packages.sentiment.workflow as workflow

    original_classifier = workflow.classify_sentiment

    def fake_resolve_target_paper_metadata(target: TargetPaper) -> TargetPaper:
        _ = target
        return target_paper

    def fake_fetch_citation_candidates_with_live_clients(target_paper: TargetPaper, max_results: int = 20) -> CitationFetchResult:
        _ = target_paper
        _ = max_results
        from packages.citation_sources.models import FetchSummary

        return CitationFetchResult(
            citing_papers=citing_papers,
            source_trace=[],
            fetch_summary=FetchSummary(
                target_query=target_paper.doi or target_paper.title or "unknown",
                target_title=target_paper.title,
                target_doi=target_paper.doi,
                target_resolve_status=target_paper.resolve_status,
                semantic_scholar_candidates=len(citing_papers),
                crossref_candidates=len(citing_papers),
                merged_candidates=len(citing_papers),
                deduped_candidates=len(citing_papers),
                partial_failure=False,
            ),
            errors=[],
        )

    def fake_analyze_author_intel_with_live_clients(citing_papers_input):
        return analyze_author_intel(
            citing_papers=list(citing_papers_input),
            openalex_client=FakeOpenAlexClient(),
            dblp_client=FakeDBLPClient(),
        )

    def fake_analyze_citation_sentiments(*args, **kwargs):
        from packages.sentiment.service import analyze_citation_sentiments

        kwargs["llm_reference_matcher"] = fake_reference_matcher
        return analyze_citation_sentiments(*args, **kwargs)

    nodes.resolve_target_paper_metadata = fake_resolve_target_paper_metadata
    nodes.fetch_citation_candidates_with_live_clients = fake_fetch_citation_candidates_with_live_clients
    nodes.analyze_author_intel_with_live_clients = fake_analyze_author_intel_with_live_clients
    nodes.analyze_citation_sentiments = fake_analyze_citation_sentiments
    workflow.classify_sentiment = fake_classify_sentiment

    try:
        state = run_analysis("请查看 DOI 为 10.1145/3368089.3409740 的论文有哪些施引文献、重点学者和引用情感")
    finally:
        nodes.resolve_target_paper_metadata = original_resolve
        nodes.fetch_citation_candidates_with_live_clients = original_fetch
        nodes.analyze_author_intel_with_live_clients = original_author_intel
        nodes.analyze_citation_sentiments = original_sentiment
        workflow.classify_sentiment = original_classifier
        shutil.rmtree(temp_dir, ignore_errors=True)

    assert state["status"] == "report_generated", state["status"]
    assert len(state["citing_papers"]) == 5, len(state["citing_papers"])
    assert len(state["scholar_labels"]) >= 1, state["scholar_labels"]
    assert len(state["citation_contexts"]) == 5, len(state["citation_contexts"])
    assert state["report_artifact"].export_paths["html"], state["report_artifact"]
    assert Path(state["report_artifact"].export_paths["html"]).exists()
    assert Path(state["report_artifact"].export_paths["json"]).exists()
    assert Path(state["report_artifact"].export_paths["pdf"]).exists()
    assert state["sentiment_summary"].unknown_count >= 1, state["sentiment_summary"]
    return state


def main() -> None:
    """Run this module as a command-line validation or utility entry point."""
    logger = StageLogger("e2e")
    logger.start()
    state = assert_e2e_mvp_real_sample()
    logger.pass_case(
        "fixture_backed_real_sample",
        detail=(
            f"sample_path={DEFAULT_SAMPLE_PATH} status={state['status']} "
            f"html={state['report_artifact'].export_paths['html']} "
            f"json={state['report_artifact'].export_paths['json']} "
            f"pdf={state['report_artifact'].export_paths['pdf']} "
            f"unknown={state['sentiment_summary'].unknown_count} errors={len(state['errors'])}"
        ),
    )
    logger.done("e2e MVP validation passed")


if __name__ == "__main__":
    main()
