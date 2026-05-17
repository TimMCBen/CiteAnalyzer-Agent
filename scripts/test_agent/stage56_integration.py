from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from apps.analyzer import nodes
from packages.citation_sources.models import CitingPaper
from packages.sentiment.models import CitationContext, FullTextDocument, SentimentAnalysisResult, SentimentSummary
from packages.shared.models import AnalysisState, AuthorProfile, AuthorSummary, ScholarLabel, TargetPaper
from scripts.test_agent.stage_logging import StageLogger


def fake_author_intel(citing_papers: list[CitingPaper]):
    _ = citing_papers
    from packages.author_intel.models import AuthorIntelResult

    return AuthorIntelResult(
        author_profiles=[
            AuthorProfile(
                author_id="author-1",
                name="Alice Smith",
                source_ids={"openalex": "A1"},
                affiliations=["Tsinghua University"],
                fields=["NLP"],
                h_index=42,
                evidence_sources=["openalex"],
            )
        ],
        scholar_labels=[
            ScholarLabel(
                author_id="author-1",
                label="heavyweight_candidate",
                evidence=["h_index=42", "citation_frequency=2"],
                confidence_note="matched_openalex_or_dblp_profile",
                trigger_rules=["h_index>=30", "frequency>=2"],
            )
        ],
        author_summary=AuthorSummary(
            total_authors=1,
            matched_profiles=1,
            heavyweight_candidates=1,
        ),
    )


def fake_fetch_fulltext_document(
    citing_paper: CitingPaper,
    search_arxiv_fallback: bool = True,
    save_dir: Path | None = None,
):
    _ = search_arxiv_fallback
    _ = save_dir
    return FullTextDocument(
        citing_paper_id=citing_paper.canonical_id,
        text=f"Full text for {citing_paper.title}",
        source_type="html",
        source_label="fixture",
    )


def fake_analyze_sentiments(
    target_paper: TargetPaper,
    citing_papers: list[CitingPaper],
    fulltext_documents=None,
    allow_network: bool = True,
    search_arxiv_fallback: bool = True,
    **_: object,
):
    _ = target_paper
    _ = allow_network
    _ = search_arxiv_fallback
    assert isinstance(fulltext_documents, dict), fulltext_documents
    return SentimentAnalysisResult(
        contexts=[
            CitationContext(
                citing_paper_id=paper.canonical_id,
                sentiment_label="neutral",
                context_text=fulltext_documents[paper.canonical_id].text,
                matched_target_reference="fixture-reference",
                evidence_note="fixture",
                text_source_type="html",
                text_source_label="fixture",
            )
            for paper in citing_papers
        ],
        summary=SentimentSummary(
            total_candidates=len(citing_papers),
            fulltext_available=len(citing_papers),
            context_found=len(citing_papers),
            classified_count=len(citing_papers),
        ),
    )


def assert_stage56_node_integration():
    original_author_intel = nodes.analyze_author_intel_with_live_clients
    original_fetch_fulltext = nodes.fetch_fulltext_document
    original_analyze_sentiments = nodes.analyze_citation_sentiments

    nodes.analyze_author_intel_with_live_clients = fake_author_intel
    nodes.fetch_fulltext_document = fake_fetch_fulltext_document
    nodes.analyze_citation_sentiments = fake_analyze_sentiments
    try:
        state: AnalysisState = AnalysisState(
            target_paper=TargetPaper(
                canonical_id="target-1",
                paper_query="10.1000/target",
                paper_query_type="doi",
                title="Target Paper",
                doi="10.1000/target",
                source_ids={"doi": "10.1000/target"},
                resolve_status="resolved",
            ),
            citing_papers=[
                CitingPaper(
                    canonical_id="citing-1",
                    title="A citing paper",
                    doi="10.1000/citing1",
                    authors=["Alice Smith"],
                )
            ],
            errors=[],
            status="citations_fetched",
        )

        state = nodes.analyze_author_intel_node(state)
        state = nodes.fetch_fulltext_documents_node(state)
        state = nodes.analyze_citation_sentiments_node(state)

        assert state["status"] == "citation_sentiments_analyzed", state["status"]
        assert len(state["author_profiles"]) == 1
        assert state["scholar_labels"][0].label == "heavyweight_candidate"
        assert "citing-1" in state["fulltext_documents"]
        assert state["citation_contexts"][0].matched_target_reference == "fixture-reference"
        assert state["sentiment_summary"].classified_count == 1
        return state
    finally:
        nodes.analyze_author_intel_with_live_clients = original_author_intel
        nodes.fetch_fulltext_document = original_fetch_fulltext
        nodes.analyze_citation_sentiments = original_analyze_sentiments


def main() -> None:
    logger = StageLogger("stage56")
    logger.start()
    state = assert_stage56_node_integration()
    logger.pass_case(
        "node_integration",
        detail=(
            "nodes=author_intel,fulltext,sentiment "
            f"citing_papers={len(state['citing_papers'])} "
            f"author_profiles={len(state['author_profiles'])} "
            f"fulltext_documents={len(state['fulltext_documents'])} "
            f"citation_contexts={len(state['citation_contexts'])}"
        ),
    )
    logger.done("stage56 integration validation passed")


if __name__ == "__main__":
    main()
