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
from packages.citation_sources.models import FetchSummary, SourceTrace
from packages.reporting.service import build_report_artifact
from packages.sentiment.models import CitationContext, SentimentSummary
from packages.shared.models import AuthorProfile, AuthorSummary, ScholarLabel, TargetPaper
from scripts.test_agent.stage_logging import StageLogger


def assert_stage7_reporting_contract() -> dict[str, object]:
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
                    label="weak_signal_candidate",
                    evidence=["institution=Tsinghua University"],
                    confidence_note="evidence_insufficient",
                    trigger_rules=["frequency>=1"],
                )
            ],
            author_summary=AuthorSummary(
                total_authors=1,
                matched_profiles=1,
                weak_signal_candidates=1,
            ),
            citation_contexts=[
                CitationContext(
                    citing_paper_id="citing-1",
                    sentiment_label="unknown",
                    context_text=None,
                    matched_target_reference=None,
                    evidence_note="no_fulltext_available",
                    text_source_type="unknown",
                    text_source_label=None,
                )
            ],
            sentiment_summary=SentimentSummary(
                total_candidates=1,
                fulltext_available=0,
                context_found=0,
                classified_count=0,
                unknown_count=1,
                label_counts={
                    "positive": 0,
                    "neutral": 0,
                    "critical": 0,
                    "unknown": 1,
                },
            ),
            fetch_summary=FetchSummary(
                target_query="10.1000/target",
                target_title="Target Paper",
                target_doi="10.1000/target",
                target_resolve_status="resolved",
                semantic_scholar_candidates=1,
                crossref_candidates=0,
                merged_candidates=1,
                deduped_candidates=1,
                partial_failure=True,
                notes=["crossref_timeout"],
            ),
            source_trace=[
                SourceTrace(
                    candidate_id="citing-1",
                    source_name="semantic_scholar",
                    source_record_id="S1",
                    query_used="10.1000/target",
                    fetched_at="2026-05-05T00:00:00Z",
                )
            ],
            state_errors=["stage5:citing-1:no_fulltext"],
            output_dir=output_dir,
        )

        html_path = Path(artifact.export_paths["html"])
        json_path = Path(artifact.export_paths["json"])
        assert html_path.exists(), html_path
        assert json_path.exists(), json_path

        payload = json.loads(json_path.read_text(encoding="utf-8"))
        assert payload["summary"]["target_title"] == "Target Paper", payload
        assert payload["summary"]["key_findings"], payload["summary"]
        assert payload["summary"]["partial_failure"] is True, payload["summary"]
        assert payload["summary"]["source_trace_count"] == 1, payload["summary"]
        assert payload["summary"]["source_trace_sources"] == ["semantic_scholar"], payload["summary"]
        assert any("crossref_timeout" in item for item in payload["summary"]["manual_attention_items"]), payload["summary"]
        assert any("stage5:citing-1:no_fulltext" in item for item in payload["summary"]["manual_attention_items"]), payload["summary"]
        assert any("evidence_insufficient" in item for item in payload["summary"]["manual_attention_items"]), payload["summary"]
        assert "year_trend" in payload["charts"], payload["charts"]
        assert "source_map" in payload["charts"], payload["charts"]
        assert "scholar_distribution" in payload["charts"], payload["charts"]
        assert "sentiment_distribution" in payload["charts"], payload["charts"]

        html = html_path.read_text(encoding="utf-8")
        assert "Target Paper" in html
        assert "Key Findings" in html
        assert "Manual Attention Items" in html
        assert "Citation Contexts" in html
        assert 'class="hero"' in html
        assert 'class="page-nav"' in html
        assert 'class="metric-grid"' in html
        assert 'class="attention-list"' in html
        assert 'class="context-list"' in html
        return {
            "output_dir": str(output_dir),
            "html_path": str(html_path),
            "json_path": str(json_path),
            "chart_keys": sorted(payload["charts"].keys()),
            "manual_attention_count": len(payload["summary"]["manual_attention_items"]),
        }
    finally:
        shutil.rmtree(output_dir, ignore_errors=True)


def main() -> None:
    logger = StageLogger("stage7")
    logger.start()
    detail = assert_stage7_reporting_contract()
    logger.pass_case(
        "reporting_contract",
        detail=(
            f"output_dir={detail['output_dir']} html={detail['html_path']} json={detail['json_path']} "
            f"charts={detail['chart_keys']} manual_attention_count={detail['manual_attention_count']}"
        ),
    )
    logger.done("stage7 validation passed")


if __name__ == "__main__":
    main()
