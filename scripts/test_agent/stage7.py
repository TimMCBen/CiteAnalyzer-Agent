from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.citation_sources.models import CitingPaper
from packages.reporting.service import build_report_artifact
from packages.sentiment.models import CitationContext, SentimentSummary
from packages.shared.models import AuthorProfile, AuthorSummary, ScholarLabel, TargetPaper


def assert_stage7_reporting_contract() -> None:
    output_dir = Path(tempfile.mkdtemp(prefix="stage7-report-", dir=REPO_ROOT))
    try:
        artifact = build_report_artifact(
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
                    year=2024,
                    authors=["Alice Smith"],
                )
            ],
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
            citation_contexts=[
                CitationContext(
                    citing_paper_id="citing-1",
                    sentiment_label="neutral",
                    context_text="We use the target work as background.",
                    matched_target_reference="fixture-reference",
                    evidence_note="fixture",
                    text_source_type="html",
                    text_source_label="fixture",
                )
            ],
            sentiment_summary=SentimentSummary(
                total_candidates=1,
                fulltext_available=1,
                context_found=1,
                classified_count=1,
                label_counts={
                    "positive": 0,
                    "neutral": 1,
                    "critical": 0,
                    "unknown": 0,
                },
            ),
            output_dir=output_dir,
        )

        html_path = Path(artifact.export_paths["html"])
        json_path = Path(artifact.export_paths["json"])
        assert html_path.exists(), html_path
        assert json_path.exists(), json_path

        payload = json.loads(json_path.read_text(encoding="utf-8"))
        assert payload["summary"]["target_title"] == "Target Paper", payload
        assert payload["summary"]["key_findings"], payload["summary"]
        assert "year_trend" in payload["charts"], payload["charts"]
        assert "source_map" in payload["charts"], payload["charts"]
        assert "scholar_distribution" in payload["charts"], payload["charts"]
        assert "sentiment_distribution" in payload["charts"], payload["charts"]

        html = html_path.read_text(encoding="utf-8")
        assert "Target Paper" in html
        assert "Key Findings" in html
        assert "Manual Attention Items" in html
        assert "Citation Contexts" in html
    finally:
        shutil.rmtree(output_dir, ignore_errors=True)


def main() -> None:
    assert_stage7_reporting_contract()
    print("[PASS] stage7::reporting_contract")
    print("stage7 validation passed")


if __name__ == "__main__":
    main()
