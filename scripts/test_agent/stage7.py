"""Validate Stage 7 report artifact structure and chart contracts."""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.citation_sources.models import CitingPaper
from packages.citation_sources.models import FetchSummary, SourceTrace
from packages.reporting.country_resolution import LLMCountryResolver, RuleBasedCountryResolver
from packages.reporting.service import build_report_artifact
from packages.sentiment.models import CitationContext, SentimentSummary
from packages.shared.models import AuthorProfile, AuthorSummary, ScholarLabel, TargetPaper
from scripts.test_agent.stage_logging import StageLogger


def assert_stage7_reporting_contract() -> dict[str, object]:
    output_dir = Path(tempfile.mkdtemp(prefix="stage7-report-", dir=REPO_ROOT))
    class RecordingCountryResolver:
        """Record whether Stage 7 uses batch country resolution."""
        def __init__(self) -> None:
            self.rule_resolver = RuleBasedCountryResolver()
            self.batch_calls: list[list[str]] = []

        def resolve(self, institution: str):
            """Resolve one institution through deterministic country rules."""
            return self.rule_resolver.resolve(institution)

        def resolve_many(self, institutions: list[str]):
            """Record batch inputs and resolve each item through rules."""
            self.batch_calls.append(list(institutions))
            return {institution: self.resolve(institution) for institution in institutions}

    country_resolver = RecordingCountryResolver()
    try:
        artifact = build_report_artifact(
            target_paper=TargetPaper(
                canonical_id="2507.19457",
                paper_query="2507.19457",
                paper_query_type="arxiv",
                title="Target Paper",
                doi=None,
                source_ids={"arxiv": "2507.19457"},
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
                ),
                CitationContext(
                    citing_paper_id="citing-2",
                    sentiment_label="neutral",
                    context_text="The same citing paper cites the target again in a taxonomy list.",
                    matched_target_reference="Target Paper",
                    evidence_note="matched_by_fixture; llm_sentiment:同一篇施引论文再次把目标论文作为分类归纳中的相关工作列出。",
                    text_source_type="pdf",
                    text_source_label="fixture.pdf",
                )
            ],
            sentiment_summary=SentimentSummary(
                total_candidates=3,
                fulltext_available=2,
                context_found=2,
                classified_count=2,
                unknown_count=1,
                label_counts={
                    "positive": 0,
                    "neutral": 2,
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
            author_identity_skipped_papers=[
                {
                    "citing_paper_id": "citing-3",
                    "title": "Third citing paper",
                    "reason": "paper_confidence_low",
                    "paper_match_confidence": "low",
                    "openalex_work_status": "title_hit_mismatch",
                    "author_resolution_status": "skipped_due_to_paper_mismatch",
                    "selected_work_id": "",
                }
            ],
            output_dir=output_dir,
            country_resolver=country_resolver,
            title_translator=lambda title: "目标论文",
            executive_summary_builder=lambda facts: [
                f"本次共识别 {facts['citation_count']} 篇施引文献，形成当前可复核的数据快照。",
                (
                    f"在 {facts['citation_count']} 篇施引文献中，{facts['classified_sentiments']} 篇已完成引用情感判断，"
                    f"{facts['unknown_sentiments']} 篇因全文不可用、引用上下文未命中或证据不足暂未判断。"
                ),
                (
                    f"系统按 h-index 与施引频次筛出 {facts['important_scholar_candidates']} 位重要学者候选，"
                    f"其中重量级候选 {facts['heavyweight_candidates']} 位、高影响力候选 {facts['high_impact_candidates']} 位。"
                ),
                (
                    f"本次共识别 {facts['dedup_author_count']} 位去重施引作者，其中 {facts['country_located_count']} 位可定位国家/地区，"
                    f"另有 {facts['country_unknown_count']} 位缺少可定位国家信息。"
                ),
            ],
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
        assert payload["summary"]["target_title_zh"] == "目标论文", payload
        assert payload["summary"]["target_doi"] is None, payload
        assert payload["summary"]["target_arxiv_id"] == "2507.19457", payload
        assert payload["summary"]["target_arxiv_url"] == "https://arxiv.org/abs/2507.19457", payload
        assert payload["contexts"][0]["sentiment_label"] == "unknown", payload["contexts"]
        assert payload["summary"]["key_findings"], payload["summary"]
        assert payload["summary"]["partial_failure"] is True, payload["summary"]
        assert payload["summary"]["source_trace_count"] == 1, payload["summary"]
        assert payload["summary"]["source_trace_sources"] == ["semantic_scholar"], payload["summary"]
        assert any("crossref_timeout" in item for item in payload["summary"]["manual_attention_items"]), payload["summary"]
        assert any("stage5:citing-1:no_fulltext" in item for item in payload["summary"]["manual_attention_items"]), payload["summary"]
        assert any("evidence_insufficient" in item for item in payload["summary"]["manual_attention_items"]), payload["summary"]
        assert any("author_identity_skip:citing-3" in item for item in payload["summary"]["manual_attention_items"]), payload["summary"]
        assert payload["summary"]["author_identity_skipped_papers"][0]["reason"] == "paper_confidence_low", payload["summary"]
        assert payload["provenance"]["author_identity_skipped_papers"][0]["citing_paper_id"] == "citing-3", payload["provenance"]
        assert "year_trend" in payload["charts"], payload["charts"]
        assert "institution_distribution" in payload["charts"], payload["charts"]
        assert "country_distribution" in payload["charts"], payload["charts"]
        assert "source_map" in payload["charts"], payload["charts"]
        assert "scholar_distribution" in payload["charts"], payload["charts"]
        assert "h_index_distribution" in payload["charts"], payload["charts"]
        assert "sentiment_distribution" in payload["charts"], payload["charts"]
        assert payload["charts"]["year_trend"] == {"2024": 1, "2025": 2}, payload["charts"]
        assert payload["charts"]["institution_distribution"] == payload["charts"]["source_map"], payload["charts"]
        assert payload["charts"]["country_distribution"]["China"] == 2, payload["charts"]
        assert payload["charts"]["country_distribution"]["United States"] == 1, payload["charts"]
        assert country_resolver.batch_calls == [["Tsinghua University", "Peking University", "MIT"]], country_resolver.batch_calls
        assert payload["charts"]["sentiment_distribution"]["unknown"] == 1, payload["charts"]
        assert payload["charts"]["sentiment_distribution"]["neutral"] == 2, payload["charts"]
        assert payload["charts"]["h_index_distribution"]["10-19"] == 1, payload["charts"]
        assert payload["charts"]["h_index_distribution"]["30-49"] == 2, payload["charts"]
        assert payload["summary"]["executive_summary"], payload["summary"]
        assert payload["provenance"]["executive_summary_source"] == "custom_builder", payload["provenance"]
        assert "全文不可用、引用上下文未命中或证据不足" in "\n".join(payload["summary"]["executive_summary"]), payload["summary"]
        assert "去重施引作者" in "\n".join(payload["summary"]["executive_summary"]), payload["summary"]
        assert payload["summary"]["top_scholars"], payload["summary"]
        assert payload["summary"]["representative_contexts"]["neutral"], payload["summary"]
        assert payload["summary"]["representative_contexts"]["neutral"][0]["citing_paper_title"] == "Another citing paper", payload["summary"]
        assert payload["summary"]["representative_contexts"]["neutral"][0]["reason"] == "中性背景引用", payload["summary"]
        assert payload["summary"]["pdf_export_status"] == "generated", payload["summary"]
        assert payload["provenance"]["pdf_export_status"] == "generated", payload["provenance"]
        assert payload["provenance"]["country_resolution_trace"], payload["provenance"]

        html = html_path.read_text(encoding="utf-8")
        assert "Target Paper" in html
        assert "分析摘要" in html
        assert "全文不可用、引用上下文未命中或证据不足" in html
        assert "去重施引作者" in html
        assert "Unknown 当前最多" not in html
        assert "重要学者" in html
        assert "作者画像跳过说明" in html
        assert "paper_confidence_low" in html
        assert "Stage 4 只使用可信 OpenAlex work.authorships.author.id" in html
        assert "代表性引用语境" in html
        assert "不伪装成趋势图" not in html
        assert "地图只展示能匹配 GeoJSON" not in html
        assert "h-index ≥ 30" in html
        assert "出现 ≥ 2 次" in html
        assert "work-authorship" in html
        assert "<details class='citation-detail'>" in html
        assert "Another citing paper" in html
        assert "引用内容：" in html
        assert "原因：" in html
        assert "llm_sentiment:" not in html
        assert "中文标题" in html
        assert "目标论文" in html
        assert "DOI:</strong> N/A" in html
        assert "https://arxiv.org/abs/2507.19457" in html
        assert "施引来源国家/地区地图" in html
        assert "调试附录" in html
        assert "补充发现" in html
        assert "系统关注项与处理提示" in html
        assert "全量引用上下文" in html
        assert "Key Findings" not in html
        assert "Manual Attention Items" not in html
        assert "Citation Contexts" not in html
        assert ">未知<" in html
        assert "echarts.min.js" in html
        assert 'id="chart-data"' in html
        assert 'id="yearTrendChart"' in html
        assert 'id="scholarDistributionChart"' in html
        assert 'id="hIndexDistributionChart"' in html
        assert 'id="sentimentDistributionChart"' in html
        assert 'id="countryDistributionChart"' in html
        assert 'id="institutionDistributionChart"' not in html
        assert 'id="world-geojson"' in html
        assert "echarts.registerMap" in html
        assert 'type: "map"' in html
        assert "visualMap" in html
        assert "United States of America" in html
        assert 'type: "pie"' in html
        assert "作者 h-index 分布" in html
        assert "学者质量分布" in html
        assert "普通学者" in html
        assert 'label: { show: true' in html
        assert "施引作者机构分布" in html
        chart_match = re.search(r'<script type="application/json" id="chart-data">(.*?)</script>', html, re.S)
        assert chart_match, html
        chart_data = json.loads(chart_match.group(1))
        institution_fallback_labels = list(chart_data["institutionDistribution"]["fallback"].keys())
        assert chart_data["institutionDistribution"]["labels"] == list(reversed(institution_fallback_labels)), chart_data["institutionDistribution"]
        assert "Source Map" not in html
        assert 'href="#author-profile-breakdown"' not in html
        assert 'href="#author-skips"' not in html
        assert 'href="#attention"' not in html
        assert 'href="#contexts"' not in html
        assert 'href="#metrics"' not in html
        assert 'href="#quality">数据覆盖</a>' in html
        assert "查看 6 条人工关注项" in html
        assert 'data-chart-state="chart"' in html
        assert "Others" not in payload["charts"]["source_map"], payload["charts"]
        assert 'class="hero"' in html
        assert 'class="top-left"' in html
        assert 'class="top-right"' in html
        assert 'class="card list-card top-summary"' in html
        assert 'class="metric-grid"' not in html
        assert 'class="stat-card"' not in html
        assert 'class="card quality-panel report-coverage"' in html
        assert 'id="quality"' in html
        assert 'class="summary-quality"' not in html
        assert 'class="page-nav"' in html
        assert 'class="chart-grid"' not in html
        assert 'class="side-chart-grid"' in html
        assert 'class="top-chart-grid"' not in html
        assert html.count("grid-template-columns: minmax(0, 760px) minmax(620px, 1fr)") == 2
        assert html.find('class="side-chart-grid" id="charts"') < html.find('<section class="report-grid">')
        assert html.find('class="side-chart-grid" id="charts"') < html.find('id="scholars"')
        assert "grid-template-columns: 1fr" in html
        assert "repeat(2, minmax(260px, 1fr))" in html
        assert ".side-chart-grid .chart-panel { height: 140px" in html
        assert ".primary-column { max-width: 760px" in html
        assert "@media (max-width: 1240px)" in html
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
    if not os.getenv("API_KEY", "").strip():
        logger.skip("live_llm_country_resolution", reason="missing_api_key")
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
    """Run Stage 7 report contract and optional live country-resolution checks."""
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
