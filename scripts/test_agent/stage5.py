from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.citation_sources.models import CitingPaper
from packages.sentiment import FullTextDocument, analyze_citation_sentiments
from packages.shared.models import TargetPaper

DEFAULT_SAMPLE_PATH = REPO_ROOT / "docs" / "generated" / "stage2-live-10.1145.3368089.3409740.json"


def load_stage2_sample(sample_path: Path) -> tuple[TargetPaper, list[CitingPaper]]:
    payload = json.loads(sample_path.read_text(encoding="utf-8"))
    fetch_result = payload["fetch_result"]

    target_paper = TargetPaper(
        canonical_id=None,
        paper_query=payload["target_doi"],
        paper_query_type="doi",
        title=None,
        doi=payload["target_doi"],
        source_ids={"doi": payload["target_doi"]},
        resolve_status="resolved",
    )

    citing_papers = [
        CitingPaper(
            canonical_id=item["canonical_id"],
            title=item["title"],
            doi=item.get("doi"),
            year=item.get("year"),
            authors=list(item.get("authors") or []),
            venue=item.get("venue"),
            abstract=item.get("abstract"),
            source_links=dict(item.get("source_links") or {}),
            source_names=list(item.get("source_names") or []),
            source_specific_ids=dict(item.get("source_specific_ids") or {}),
        )
        for item in fetch_result["citing_papers"]
    ]
    return target_paper, citing_papers


def build_fulltext_fixtures(target_doi: str) -> dict[str, FullTextDocument]:
    return {
        "citing-1": FullTextDocument(
            citing_paper_id="citing-1",
            source_type="markdown",
            source_label="local-fixture-positive.md",
            text=(
                f"Our detector explicitly builds on the vulnerability model introduced in {target_doi}. "
                "Following that work, we extend the analysis pipeline to identify open-secret attack paths."
            ),
        ),
        "citing-2": FullTextDocument(
            citing_paper_id="citing-2",
            source_type="markdown",
            source_label="local-fixture-neutral.md",
            text=(
                f"We cite {target_doi} as background literature on smart-contract transparency and human-centric concerns. "
                "The paper is referenced here to frame the surrounding design space rather than to evaluate its claims."
            ),
        ),
        "citing-3": FullTextDocument(
            citing_paper_id="citing-3",
            source_type="latex",
            source_label="local-fixture-critical.tex",
            text=(
                f"However, {target_doi} does not model fairness constraints and cannot explain fund-stealing scenarios in DeFi protocols. "
                "This limitation motivates our fairness validation design."
            ),
        ),
        "citing-5": FullTextDocument(
            citing_paper_id="citing-5",
            source_type="markdown",
            source_label="local-fixture-unknown.md",
            text=(
                "We discuss ERC compliance, symbolic execution, and LLM-guided auditing. "
                "This section intentionally omits any direct mention of the target paper."
            ),
        ),
    }


def assert_stage5_local_validation(sample_path: Path = DEFAULT_SAMPLE_PATH) -> None:
    target_paper, citing_papers = load_stage2_sample(sample_path)
    result = analyze_citation_sentiments(
        target_paper=target_paper,
        citing_papers=citing_papers,
        fulltext_documents=build_fulltext_fixtures(target_paper.doi or ""),
    )

    labels = {context.citing_paper_id: context.sentiment_label for context in result.contexts}
    evidence_notes = {context.citing_paper_id: context.evidence_note for context in result.contexts}
    source_types = {context.citing_paper_id: context.text_source_type for context in result.contexts}

    assert len(result.contexts) == 5, f"expected 5 citation contexts, got {len(result.contexts)}"
    assert labels["citing-1"] == "positive", labels
    assert labels["citing-2"] == "neutral", labels
    assert labels["citing-3"] == "critical", labels
    assert labels["citing-4"] == "unknown", labels
    assert labels["citing-5"] == "unknown", labels

    assert evidence_notes["citing-1"].startswith("matched_by_doi; rule_positive"), evidence_notes["citing-1"]
    assert evidence_notes["citing-2"].endswith("default_neutral_without_polarized_cues"), evidence_notes["citing-2"]
    assert "rule_critical" in evidence_notes["citing-3"], evidence_notes["citing-3"]
    assert evidence_notes["citing-4"] == "no_text_available", evidence_notes["citing-4"]
    assert evidence_notes["citing-5"] == "target_reference_not_found", evidence_notes["citing-5"]
    assert source_types["citing-4"] == "unknown", source_types

    summary = result.summary
    assert summary.total_candidates == 5, summary
    assert summary.fulltext_available == 4, summary
    assert summary.context_found == 3, summary
    assert summary.classified_count == 3, summary
    assert summary.unknown_count == 2, summary
    assert summary.label_counts == {
        "positive": 1,
        "neutral": 1,
        "critical": 1,
        "unknown": 2,
    }, summary.label_counts


def main() -> None:
    assert_stage5_local_validation()
    print("[PASS] stage5::local_sentiment_validation")
    print("stage5 validation passed")


if __name__ == "__main__":
    main()
