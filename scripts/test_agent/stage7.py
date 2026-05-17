"""Command-line validation helpers for stage7."""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.citation_sources.models import CitingPaper
from packages.citation_sources.models import FetchSummary, SourceTrace
from packages.reporting.country_resolution import LLMCountryResolver
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
                ),
                CitingPaper(
                    canonical_id="citing-2",
                    title="Another citing paper",
                    doi="10.1000/citing2",
                    year=2025,
                    authors=["Bob Chen"],
                ),
                CitingPaper(
                    canonical_id="citing-3",
                    title="Third citing paper",
                    doi="10.1000/citing3",
                    year=2025,
                    authors=["Carol Li"],
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
                ),
                AuthorProfile(
                    author_id="author-2",
                    name="Bob Chen",
                    affiliations=["Peking University"],
                    fields=["NLP"],
                    h_index=12,
                    evidence_sources=["openalex"],
                ),
                AuthorProfile(
                    author_id="author-3",
                    name="Carol Li",
                    affiliations=["MIT"],
                    fields=["AI"],
                    h_index=31,
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
                ),
                ScholarLabel(
                    author_id="author-3",
                    label="high_impact_candidate",
                    evidence=["h_index=31"],
                    confidence_note="matched_openalex_or_dblp_profile",
                    trigger_rules=["h_index>=30"],
                )
            ],
            author_summary=AuthorSummary(
                total_authors=3,
                matched_profiles=3,
                high_impact_candidates=1,
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
                ),
                CitationContext(
                    citing_paper_id="citing-2",
                    sentiment_label="neutral",
                    context_text="This citing paper mentions the target as related work.",
                    matched_target_reference="Target Paper",
                    evidence_note="matched_by_fixture; llm_sentiment:中性背景引用",
                    text_source_type="pdf",
                    text_source_label="fixture.pdf",
                )
            ],
            sentiment_summary=SentimentSummary(
                total_candidates=2,
                fulltext_available=1,
                context_found=1,
                classified_count=1,
                unknown_count=1,
                label_counts={
                    "positive": 0,
                    "neutral": 1,
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
        pdf_path = Path(artifact.export_paths["pdf"])
        assert html_path.exists(), html_path
        assert json_path.exists(), json_path
        assert pdf_path.exists(), pdf_path
        assert pdf_path.stat().st_size > 0, pdf_path

        payload = json.loads(json_path.read_text(encoding="utf-8"))
        assert payload["summary"]["target_title"] == "Target Paper", payload
        assert payload["contexts"][0]["sentiment_label"] == "unknown", payload["contexts"]
        assert payload["summary"]["key_findings"], payload["summary"]
        assert payload["summary"]["partial_failure"] is True, payload["summary"]
        assert payload["summary"]["source_trace_count"] == 1, payload["summary"]
        assert payload["summary"]["source_trace_sources"] == ["semantic_scholar"], payload["summary"]
        assert any("crossref_timeout" in item for item in payload["summary"]["manual_attention_items"]), payload["summary"]
        assert any("stage5:citing-1:no_fulltext" in item for item in payload["summary"]["manual_attention_items"]), payload["summary"]
        assert any("evidence_insufficient" in item for item in payload["summary"]["manual_attention_items"]), payload["summary"]
        assert "year_trend" in payload["charts"], payload["charts"]
        assert "institution_distribution" in payload["charts"], payload["charts"]
        assert "country_distribution" in payload["charts"], payload["charts"]
        assert "source_map" in payload["charts"], payload["charts"]
        assert "scholar_distribution" in payload["charts"], payload["charts"]
        assert "sentiment_distribution" in payload["charts"], payload["charts"]
        assert payload["charts"]["year_trend"] == {"2024": 1, "2025": 2}, payload["charts"]
        assert payload["charts"]["institution_distribution"] == payload["charts"]["source_map"], payload["charts"]
        assert payload["charts"]["country_distribution"]["China"] == 2, payload["charts"]
        assert payload["charts"]["country_distribution"]["United States"] == 1, payload["charts"]
        assert payload["charts"]["sentiment_distribution"]["unknown"] == 1, payload["charts"]
        assert payload["charts"]["sentiment_distribution"]["neutral"] == 1, payload["charts"]
        assert payload["summary"]["executive_summary"], payload["summary"]
        assert payload["summary"]["top_scholars"], payload["summary"]
        assert payload["summary"]["representative_contexts"]["neutral"], payload["summary"]
        assert payload["summary"]["pdf_export_status"] == "generated", payload["summary"]
        assert payload["provenance"]["pdf_export_status"] == "generated", payload["provenance"]
        assert payload["provenance"]["country_resolution_trace"], payload["provenance"]

        html = html_path.read_text(encoding="utf-8")
        assert "Target Paper" in html
        assert "分析摘要" in html
        assert "重要学者" in html
        assert "代表性引用语境" in html
        assert "施引来源国家/地区分布" in html
        assert "Key Findings" in html
        assert "Manual Attention Items" in html
        assert "Citation Contexts" in html
        assert ">未知<" in html
        assert "echarts.min.js" in html
        assert 'id="chart-data"' in html
        assert 'id="yearTrendChart"' in html
        assert 'id="scholarDistributionChart"' in html
        assert 'id="sentimentDistributionChart"' in html
        assert 'id="countryDistributionChart"' in html
        assert 'id="institutionDistributionChart"' in html
        assert 'type: "pie"' in html
        assert "施引作者机构分布" in html
        assert "Source Map" not in html
        assert "查看 5 条人工关注项" in html
        assert 'data-chart-state="chart"' in html
        assert "Others" not in payload["charts"]["source_map"], payload["charts"]
        assert 'class="hero"' in html
        assert 'class="page-nav"' in html
        assert 'class="metric-grid"' in html
        assert 'class="chart-grid"' in html
        assert 'class="attention-list"' in html
        assert 'class="context-list"' in html
        return {
            "output_dir": str(output_dir),
            "html_path": str(html_path),
            "json_path": str(json_path),
            "pdf_path": str(pdf_path),
            "chart_keys": sorted(payload["charts"].keys()),
            "manual_attention_count": len(payload["summary"]["manual_attention_items"]),
        }
    finally:
        shutil.rmtree(output_dir, ignore_errors=True)


def assert_live_llm_country_resolution(logger: StageLogger) -> None:
    from apps.analyzer.config import get_llm_env_config

    if os.getenv("CI", "").strip().lower() != "true":
        logger.skip("live_llm_country_resolution", reason="ci_only")
        return

    config = get_llm_env_config(override=True)
    assert config.model == "gpt-5.4", (
        f"stage7 CI live LLM test requires MODEL=gpt-5.4 from CI env or {config.env_path}; "
        f"got MODEL={config.model}"
    )

    result = LLMCountryResolver().resolve("ETH Zurich")
    assert result.method == "llm", result
    assert result.country != "Unknown", result
    assert result.confidence in {"high", "medium", "low"}, result
    assert result.evidence, result
    logger.pass_case(
        "live_llm_country_resolution",
        detail=f"model={config.model} institution={result.institution} country={result.country} confidence={result.confidence}",
    )


def main() -> None:
    """Run this module as a command-line validation or utility entry point."""
    logger = StageLogger("stage7")
    logger.start()
    detail = assert_stage7_reporting_contract()
    logger.pass_case(
        "reporting_contract",
        detail=(
            f"output_dir={detail['output_dir']} html={detail['html_path']} json={detail['json_path']} pdf={detail['pdf_path']} "
            f"charts={detail['chart_keys']} manual_attention_count={detail['manual_attention_count']}"
        ),
    )
    assert_live_llm_country_resolution(logger)
    logger.done("stage7 validation passed")


if __name__ == "__main__":
    main()
