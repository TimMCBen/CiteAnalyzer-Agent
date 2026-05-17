from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Iterable

from packages.citation_sources.models import CitingPaper, FetchSummary, SourceTrace
from packages.sentiment.models import CitationContext, SentimentSummary
from packages.shared.models import AnalysisState, AuthorProfile, AuthorSummary, ReportArtifact, ScholarLabel, TargetPaper


DEFAULT_REPORT_DIR = Path("generated-reports")
SENTIMENT_LABEL_DISPLAY = {
    "positive": "正向",
    "neutral": "中性",
    "critical": "批评",
    "unknown": "未知",
}
SCHOLAR_LABEL_DISPLAY = {
    "heavyweight_candidate": "重量级候选",
    "high_impact_candidate": "高影响力候选",
    "weak_signal_candidate": "弱信号候选",
}
SENTIMENT_ORDER = ["critical", "neutral", "positive", "unknown"]
SENTIMENT_COLORS = {
    "critical": "#b85c42",
    "neutral": "#8f8172",
    "positive": "#6f8f5b",
    "unknown": "#b9aa96",
}
ECHARTS_CDN_URL = "https://cdn.jsdelivr.net/npm/echarts@6.0.0/dist/echarts.min.js"
INSTITUTION_TOP_N = 8


def build_report_artifact(
    target_paper: TargetPaper,
    citing_papers: list[CitingPaper],
    author_profiles: list[AuthorProfile],
    scholar_labels: list[ScholarLabel],
    author_summary: AuthorSummary,
    citation_contexts: list[CitationContext],
    sentiment_summary: SentimentSummary,
    fetch_summary: FetchSummary | None = None,
    source_trace: list[SourceTrace] | None = None,
    state_errors: list[str] | None = None,
    output_dir: Path | None = None,
) -> ReportArtifact:
    report_id = target_paper.canonical_id or target_paper.doi or target_paper.title or "unknown-target"
    safe_report_id = _slugify(report_id)
    report_dir = (output_dir or DEFAULT_REPORT_DIR).resolve() / safe_report_id
    report_dir.mkdir(parents=True, exist_ok=True)

    provenance = _build_provenance(fetch_summary, source_trace, state_errors, scholar_labels)
    chart_payloads = {
        "year_trend": _build_year_trend(citing_papers),
        "source_map": _build_source_map(author_profiles),
        "scholar_distribution": _build_scholar_distribution(scholar_labels),
        "sentiment_distribution": dict(sentiment_summary.label_counts),
    }
    summary = {
        "target_title": target_paper.title,
        "target_doi": target_paper.doi,
        "citation_count": len(citing_papers),
        "heavyweight_candidates": author_summary.heavyweight_candidates,
        "high_impact_candidates": author_summary.high_impact_candidates,
        "weak_signal_candidates": author_summary.weak_signal_candidates,
        "context_found": sentiment_summary.context_found,
        "unknown_sentiments": sentiment_summary.unknown_count,
        "partial_failure": provenance["partial_failure"],
        "source_trace_count": provenance["source_trace_count"],
        "source_trace_sources": provenance["source_trace_sources"],
        "key_findings": _build_key_findings(citing_papers, scholar_labels, sentiment_summary, provenance),
        "manual_attention_items": _build_manual_attention_items(citation_contexts, scholar_labels, provenance),
    }

    json_path = report_dir / "report.json"
    html_path = report_dir / "report.html"
    json_path.write_text(
        json.dumps(
            {
                "summary": summary,
                "charts": chart_payloads,
                "provenance": provenance,
                "contexts": [_serialize_context(context) for context in citation_contexts],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    html_path.write_text(
        _render_html(target_paper, summary, chart_payloads, provenance, citation_contexts),
        encoding="utf-8",
    )

    return ReportArtifact(
        report_id=safe_report_id,
        target_paper_id=target_paper.canonical_id or target_paper.doi or safe_report_id,
        summary=summary,
        charts=chart_payloads,
        export_paths={
            "html": str(html_path),
            "json": str(json_path),
        },
    )


def attach_report_artifact_to_state(state: AnalysisState, artifact: ReportArtifact) -> AnalysisState:
    state["report_artifact"] = artifact  # type: ignore[assignment]
    state["status"] = "report_generated"
    return state


def _build_year_trend(citing_papers: Iterable[CitingPaper]) -> dict[str, int]:
    counts = Counter(str(paper.year) for paper in citing_papers if paper.year is not None)
    return dict(sorted(counts.items()))


def _build_source_map(author_profiles: Iterable[AuthorProfile]) -> dict[str, int]:
    counts = Counter()
    for profile in author_profiles:
        if profile.affiliations:
            counts[profile.affiliations[0]] += 1
    return dict(sorted(counts.items()))


def _build_scholar_distribution(labels: Iterable[ScholarLabel]) -> dict[str, int]:
    counts = Counter(label.label for label in labels)
    return dict(sorted(counts.items()))


def _build_key_findings(
    citing_papers: list[CitingPaper],
    scholar_labels: list[ScholarLabel],
    sentiment_summary: SentimentSummary,
    provenance: dict[str, object],
) -> list[str]:
    findings = [
        f"共识别 {len(citing_papers)} 篇施引论文。",
        f"重量级学者候选 {sum(1 for label in scholar_labels if label.label == 'heavyweight_candidate')} 位。",
        f"已分类引用 {sentiment_summary.classified_count} 条，无法判断 {sentiment_summary.unknown_count} 条。",
    ]
    if provenance["partial_failure"]:
        findings.append("上游抓取或解析存在部分失败，结论需结合注意事项复核。")
    return findings


def _build_manual_attention_items(
    citation_contexts: Iterable[CitationContext],
    scholar_labels: Iterable[ScholarLabel],
    provenance: dict[str, object],
) -> list[str]:
    items = []
    for context in citation_contexts:
        if context.sentiment_label == "unknown":
            items.append(f"{context.citing_paper_id}: {context.evidence_note}")
    if provenance["partial_failure"]:
        fetch_notes = provenance["fetch_notes"] or ["partial_fetch_failure"]
        items.extend(f"fetch: {note}" for note in fetch_notes)
    items.extend(str(error) for error in provenance["state_errors"])
    for label in scholar_labels:
        if label.confidence_note:
            items.append(f"{label.author_id}: {label.label}: {label.confidence_note}")
    return items


def _build_provenance(
    fetch_summary: FetchSummary | None,
    source_trace: list[SourceTrace] | None,
    state_errors: list[str] | None,
    scholar_labels: list[ScholarLabel],
) -> dict[str, object]:
    trace = source_trace or []
    return {
        "partial_failure": bool(fetch_summary.partial_failure) if fetch_summary else False,
        "fetch_notes": list(fetch_summary.notes) if fetch_summary else [],
        "source_trace_count": len(trace),
        "source_trace_sources": sorted({item.source_name for item in trace if item.source_name}),
        "state_errors": list(state_errors or []),
        "low_confidence_labels": [
            {
                "author_id": label.author_id,
                "label": label.label,
                "confidence_note": label.confidence_note,
                "evidence": list(label.evidence),
            }
            for label in scholar_labels
            if label.confidence_note
        ],
    }


def _serialize_context(context: CitationContext) -> dict[str, object]:
    return {
        "citing_paper_id": context.citing_paper_id,
        "sentiment_label": context.sentiment_label,
        "context_text": context.context_text,
        "matched_target_reference": context.matched_target_reference,
        "evidence_note": context.evidence_note,
        "text_source_type": context.text_source_type,
        "text_source_label": context.text_source_label,
    }


def _display_sentiment_label(label: str) -> str:
    return SENTIMENT_LABEL_DISPLAY.get(label, label)


def _display_scholar_label(label: str) -> str:
    return SCHOLAR_LABEL_DISPLAY.get(label, label)


def _render_html(
    target_paper: TargetPaper,
    summary: dict[str, object],
    charts: dict[str, object],
    provenance: dict[str, object],
    citation_contexts: list[CitationContext],
) -> str:
    def render_list(items: list[str], empty_text: str = "None") -> str:
        if not items:
            return f"<li>{empty_text}</li>"
        return "".join(f"<li>{item}</li>" for item in items)

    def render_map(items: dict[str, object], empty_text: str = "No data") -> str:
        if not items:
            return f"<li>{empty_text}</li>"
        return "".join(
            f"<li><span title=\"{key}\">{key}</span><strong>{value}</strong></li>"
            for key, value in items.items()
        )

    chart_data = _build_html_chart_data(charts, summary, provenance)
    chart_data_json = _json_for_script(chart_data)

    contexts_html = "".join(
        (
            "<article class='context-card'>"
            f"<div class='context-head'><h3>{context.citing_paper_id}</h3><span class='sentiment-tag'>{_display_sentiment_label(context.sentiment_label)}</span></div>"
            f"<p><strong>evidence:</strong> {context.evidence_note}</p>"
            f"<p>{context.context_text or 'No context available.'}</p>"
            "</article>"
        )
        for context in citation_contexts
    )

    summary_metrics = [
        ("施引文献", summary.get("citation_count", 0)),
        ("重量级候选", summary.get("heavyweight_candidates", 0)),
        ("高影响力候选", summary.get("high_impact_candidates", 0)),
        ("未知情感", summary.get("unknown_sentiments", 0)),
    ]
    metric_cards = "".join(
        f"<article class='card stat-card'><span>{label}</span><strong>{value}</strong></article>"
        for label, value in summary_metrics
    )
    quality_summary = _build_quality_summary(summary, provenance)
    quality_cards = "".join(
        f"<article class='quality-chip'><span>{item['label']}</span><strong>{item['value']}</strong></article>"
        for item in quality_summary["items"]
    )
    provenance_items = [
        f"部分失败: {provenance.get('partial_failure', False)}",
        f"来源追踪: {provenance.get('source_trace_count', 0)}",
    ]
    provenance_items.extend(str(note) for note in provenance.get("fetch_notes", []))
    provenance_items.extend(str(error) for error in provenance.get("state_errors", []))
    provenance_items.extend(
        f"{item.get('author_id')}: {item.get('label')}: {item.get('confidence_note')}"
        for item in provenance.get("low_confidence_labels", [])
        if isinstance(item, dict)
    )
    attention_items = list(summary.get("manual_attention_items", []))

    year_fallback = _render_year_fallback(chart_data["yearTrend"])
    scholar_fallback = render_map(chart_data["scholarDistribution"]["fallback"])
    sentiment_fallback = render_map(chart_data["sentimentDistribution"]["fallback"])
    institution_fallback = render_map(chart_data["institutionDistribution"]["fallback"])
    attention_html = (
        "<p class='muted'>当前没有需要人工关注的项目。</p>"
        if not attention_items
        else (
            f"<details class='attention-details'><summary>查看 {len(attention_items)} 条人工关注项</summary>"
            f"<ul class='attention-list'>{render_list(attention_items)}</ul></details>"
        )
    )

    return f"""<!doctype html>
<html lang="zh">
<head>
  <meta charset="utf-8" />
  <title>CiteAnalyzer Report - {target_paper.title or 'Unknown Target'}</title>
  <script src="{ECHARTS_CDN_URL}"></script>
  <style>
    :root {{
      --bg: #f4efe6;
      --panel: #fffaf2;
      --ink: #1f2937;
      --muted: #6b7280;
      --line: #dfd1ba;
      --accent: #9f4f2b;
      --accent-soft: #f3e0ce;
      --good: #6f8f5b;
      --warn: #b58a48;
      --risk: #b85c42;
    }}
    * {{ box-sizing: border-box; }}
    body {{ font-family: Georgia, "Times New Roman", serif; margin: 0; padding: 2rem; color: var(--ink); background: linear-gradient(180deg, #efe4cf 0%, var(--bg) 100%); }}
    section {{ margin-bottom: 1.5rem; }}
    h1, h2, h3, p {{ margin-top: 0; }}
    .hero {{ border: 1px solid var(--line); border-radius: 20px; padding: 2rem; background: radial-gradient(circle at top left, #fff7eb 0%, var(--panel) 60%); box-shadow: 0 12px 30px rgba(95, 63, 38, 0.08); }}
    .hero p {{ color: var(--muted); margin-bottom: 0; }}
    .page-nav {{ display: flex; flex-wrap: wrap; gap: 0.75rem; margin: 1rem 0 1.5rem; }}
    .page-nav a {{ color: var(--accent); text-decoration: none; padding: 0.55rem 0.9rem; border: 1px solid var(--line); border-radius: 999px; background: rgba(255, 255, 255, 0.72); }}
    .metric-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1rem; }}
    .chart-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 1rem; }}
    .card {{ border: 1px solid var(--line); border-radius: 16px; padding: 1rem; background: rgba(255, 250, 242, 0.96); }}
    .stat-card span {{ display: block; color: var(--muted); font-size: 0.95rem; margin-bottom: 0.35rem; }}
    .stat-card strong {{ font-size: 1.85rem; color: var(--accent); }}
    .muted {{ color: var(--muted); }}
    .quality-panel {{ border: 1px solid var(--line); border-radius: 18px; padding: 1.25rem; background: rgba(255, 250, 242, 0.94); }}
    .quality-head {{ display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 1rem; }}
    .quality-badge {{ display: inline-flex; align-items: center; border-radius: 999px; padding: 0.35rem 0.75rem; color: #fffaf2; background: var(--good); font-weight: 700; }}
    .quality-badge[data-level="warning"] {{ background: var(--warn); }}
    .quality-badge[data-level="risk"] {{ background: var(--risk); }}
    .quality-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 0.75rem; margin-top: 1rem; }}
    .quality-chip {{ border: 1px solid var(--line); border-radius: 14px; padding: 0.75rem; background: rgba(255, 255, 255, 0.55); }}
    .quality-chip span {{ display: block; color: var(--muted); font-size: 0.9rem; }}
    .quality-chip strong {{ color: var(--accent); font-size: 1.35rem; }}
    .chart-card {{ min-height: 360px; }}
    .chart-card h2 {{ margin-bottom: 0.35rem; }}
    .chart-note {{ color: var(--muted); font-size: 0.92rem; min-height: 2.3rem; }}
    .chart-panel {{ height: 260px; min-height: 260px; margin-top: 0.5rem; }}
    .chart-card[data-chart-state="fallback"] .chart-panel {{ display: none; }}
    .chart-card[data-chart-state="chart"] .chart-fallback {{ display: none; }}
    .chart-fallback {{ margin-top: 0.75rem; }}
    .list-card ul, .attention-list, .finding-list, .data-list {{ padding-left: 1.2rem; margin: 0; }}
    .data-list li {{ display: flex; justify-content: space-between; gap: 1rem; padding: 0.2rem 0; }}
    .data-list span {{ color: var(--muted); overflow-wrap: anywhere; }}
    .attention-list li {{ color: var(--accent); }}
    .attention-details summary {{ cursor: pointer; color: var(--accent); font-weight: 700; margin-bottom: 0.75rem; }}
    .context-list {{ border: 1px solid var(--line); border-radius: 18px; padding: 1.25rem; background: rgba(255, 250, 242, 0.92); }}
    .context-card {{ border-top: 1px solid var(--line); padding-top: 1rem; margin-top: 1rem; }}
    .context-card:first-child {{ border-top: 0; margin-top: 0; padding-top: 0; }}
    .context-head {{ display: flex; justify-content: space-between; align-items: baseline; gap: 1rem; }}
    .sentiment-tag {{ color: var(--accent); font-weight: 700; text-transform: capitalize; }}
    @media (max-width: 720px) {{
      body {{ padding: 1rem; }}
      .chart-grid {{ grid-template-columns: 1fr; }}
      .chart-panel {{ height: 240px; }}
      .page-nav {{ gap: 0.45rem; }}
    }}
  </style>
</head>
<body>
  <section class="hero" id="overview">
    <h1>{target_paper.title or 'Unknown Target Paper'}</h1>
    <p><strong>DOI:</strong> {target_paper.doi or 'N/A'}</p>
  </section>
  <nav class="page-nav">
    <a href="#overview">Overview</a>
    <a href="#metrics">Metrics</a>
    <a href="#charts">Charts</a>
    <a href="#findings">Findings</a>
    <a href="#quality">Quality</a>
    <a href="#attention">Attention</a>
    <a href="#contexts">Contexts</a>
  </nav>
  <section class="metric-grid" id="metrics">
    {metric_cards}
  </section>
  <section class="quality-panel" id="quality">
    <div class="quality-head">
      <div>
        <h2>Data Quality</h2>
        <p class="muted">{quality_summary['note']}</p>
      </div>
      <span class="quality-badge" data-level="{quality_summary['level']}">{quality_summary['label']}</span>
    </div>
    <div class="quality-grid">{quality_cards}</div>
  </section>
  <section class="chart-grid" id="charts">
    <article class="card chart-card" data-chart-state="{chart_data['yearTrend']['state']}">
      <h2>引用年份趋势</h2>
      <p class="chart-note">{chart_data['yearTrend']['note']}</p>
      <div class="chart-panel" id="yearTrendChart" role="img" aria-label="引用年份趋势图"></div>
      <div class="chart-fallback">{year_fallback}</div>
    </article>
    <article class="card chart-card" data-chart-state="{chart_data['scholarDistribution']['state']}">
      <h2>学者质量分布</h2>
      <p class="chart-note">{chart_data['scholarDistribution']['note']}</p>
      <div class="chart-panel" id="scholarDistributionChart" role="img" aria-label="学者质量分布图"></div>
      <ul class="data-list chart-fallback">{scholar_fallback}</ul>
    </article>
    <article class="card chart-card" data-chart-state="{chart_data['sentimentDistribution']['state']}">
      <h2>引用情感分布</h2>
      <p class="chart-note">{chart_data['sentimentDistribution']['note']}</p>
      <div class="chart-panel" id="sentimentDistributionChart" role="img" aria-label="引用情感分布图"></div>
      <ul class="data-list chart-fallback">{sentiment_fallback}</ul>
    </article>
    <article class="card chart-card" data-chart-state="{chart_data['institutionDistribution']['state']}">
      <h2>施引作者机构分布 Top {INSTITUTION_TOP_N}</h2>
      <p class="chart-note">{chart_data['institutionDistribution']['note']}</p>
      <div class="chart-panel" id="institutionDistributionChart" role="img" aria-label="施引作者机构分布图"></div>
      <ul class="data-list chart-fallback">{institution_fallback}</ul>
    </article>
  </section>
  <section id="findings">
    <h2>Key Findings</h2>
    <ul class="finding-list">{render_list(list(summary.get('key_findings', [])), 'No findings generated')}</ul>
  </section>
  <section id="attention">
    <h2>Manual Attention Items</h2>
    <ul class="attention-list">{render_list(provenance_items, 'No quality warnings')}</ul>
    {attention_html}
  </section>
  <section id="contexts">
    <h2>Citation Contexts</h2>
    <div class="context-list">{contexts_html or '<p>No contexts available.</p>'}</div>
  </section>
  <script type="application/json" id="chart-data">{chart_data_json}</script>
  <script>
    (() => {{
      const source = document.getElementById("chart-data");
      if (!source || !window.echarts) return;
      const payload = JSON.parse(source.textContent);
      const initChart = (id, state, option) => {{
        if (state !== "chart") return;
        const element = document.getElementById(id);
        if (!element) return;
        const chart = echarts.init(element, null, {{ renderer: "svg" }});
        chart.setOption(option);
        window.addEventListener("resize", () => chart.resize());
      }};
      const axisLabel = {{ color: "#6b7280" }};
      const splitLine = {{ lineStyle: {{ color: "rgba(159, 79, 43, 0.14)" }} }};

      initChart("yearTrendChart", payload.yearTrend.state, {{
        color: ["#9f4f2b"],
        tooltip: {{ trigger: "axis" }},
        grid: {{ left: 44, right: 18, top: 24, bottom: 34 }},
        xAxis: {{ type: "category", data: payload.yearTrend.labels, axisLabel }},
        yAxis: {{ type: "value", minInterval: 1, axisLabel, splitLine }},
        series: [{{ type: "bar", data: payload.yearTrend.values, barMaxWidth: 34, itemStyle: {{ borderRadius: [8, 8, 0, 0] }} }}]
      }});

      initChart("scholarDistributionChart", payload.scholarDistribution.state, {{
        color: ["#9f4f2b"],
        tooltip: {{ trigger: "axis", axisPointer: {{ type: "shadow" }} }},
        grid: {{ left: 112, right: 22, top: 22, bottom: 26 }},
        xAxis: {{ type: "value", minInterval: 1, axisLabel, splitLine }},
        yAxis: {{ type: "category", data: payload.scholarDistribution.labels, axisLabel }},
        series: [{{ type: "bar", data: payload.scholarDistribution.values, barMaxWidth: 24, itemStyle: {{ borderRadius: [0, 8, 8, 0] }} }}]
      }});

      initChart("sentimentDistributionChart", payload.sentimentDistribution.state, {{
        tooltip: {{ trigger: "axis", axisPointer: {{ type: "shadow" }} }},
        grid: {{ left: 78, right: 22, top: 22, bottom: 26 }},
        xAxis: {{ type: "value", minInterval: 1, axisLabel, splitLine }},
        yAxis: {{ type: "category", data: payload.sentimentDistribution.labels, axisLabel }},
        series: [{{ type: "bar", data: payload.sentimentDistribution.items, barMaxWidth: 24, itemStyle: {{ color: item => item.data.color, borderRadius: [0, 8, 8, 0] }} }}]
      }});

      initChart("institutionDistributionChart", payload.institutionDistribution.state, {{
        color: ["#b58a48"],
        tooltip: {{ trigger: "axis", axisPointer: {{ type: "shadow" }} }},
        grid: {{ left: 150, right: 22, top: 22, bottom: 26 }},
        xAxis: {{ type: "value", minInterval: 1, axisLabel, splitLine }},
        yAxis: {{ type: "category", data: payload.institutionDistribution.labels, axisLabel: {{ ...axisLabel, width: 130, overflow: "truncate" }} }},
        series: [{{ type: "bar", data: payload.institutionDistribution.values, barMaxWidth: 22, itemStyle: {{ borderRadius: [0, 8, 8, 0] }} }}]
      }});
    }})();
  </script>
</body>
</html>
"""


def _build_html_chart_data(
    charts: dict[str, object],
    summary: dict[str, object],
    provenance: dict[str, object],
) -> dict[str, object]:
    year_trend = _coerce_int_map(charts.get("year_trend"))
    scholar_distribution = _coerce_int_map(charts.get("scholar_distribution"))
    sentiment_distribution = _coerce_int_map(charts.get("sentiment_distribution"))
    institution_distribution = _coerce_int_map(charts.get("source_map"))

    year_labels = list(year_trend.keys())
    year_values = list(year_trend.values())
    year_state = "chart" if len(year_labels) >= 2 else "fallback"

    scholar_items = [
        (_display_scholar_label(label), count)
        for label, count in _nonzero_items(scholar_distribution)
    ]
    scholar_state = "chart" if len(scholar_items) >= 2 else "fallback"

    sentiment_items = [
        (
            _display_sentiment_label(label),
            sentiment_distribution.get(label, 0),
            SENTIMENT_COLORS.get(label, "#9f4f2b"),
        )
        for label in SENTIMENT_ORDER
        if sentiment_distribution.get(label, 0) > 0
    ]
    sentiment_state = "chart" if len(sentiment_items) >= 2 else "fallback"

    institution_items = _top_n_with_others(institution_distribution, limit=INSTITUTION_TOP_N)
    institution_state = "chart" if len(institution_distribution) >= 3 and len(institution_items) >= 2 else "fallback"

    return {
        "yearTrend": {
            "state": year_state,
            "note": _year_trend_note(year_trend, summary),
            "labels": year_labels,
            "values": year_values,
            "fallback": year_trend,
        },
        "scholarDistribution": {
            "state": scholar_state,
            "note": "按作者画像规则聚合高影响力、重量级与弱信号候选。",
            "labels": [label for label, _ in scholar_items],
            "values": [count for _, count in scholar_items],
            "fallback": dict(scholar_items) or {"暂无学者标签": 0},
        },
        "sentimentDistribution": {
            "state": sentiment_state,
            "note": "未知表示证据不足，不应被当作普通情绪类别。",
            "labels": [label for label, _, _ in sentiment_items],
            "values": [count for _, count, _ in sentiment_items],
            "items": [
                {"value": count, "name": label, "color": color}
                for label, count, color in sentiment_items
            ],
            "fallback": {
                _display_sentiment_label(label): count
                for label, count in sentiment_distribution.items()
                if count > 0
            }
            or {"暂无情感分类": 0},
        },
        "institutionDistribution": {
            "state": institution_state,
            "note": "当前按作者首条机构文本近似聚合，不代表地理地图。",
            "labels": [label for label, _ in institution_items],
            "values": [count for _, count in institution_items],
            "fallback": dict(institution_items) or {"暂无机构信息": 0},
            "raw_count": len(institution_distribution),
        },
        "quality": _build_quality_summary(summary, provenance),
    }


def _build_quality_summary(summary: dict[str, object], provenance: dict[str, object]) -> dict[str, object]:
    unknown = _as_int(summary.get("unknown_sentiments"))
    partial_failure = bool(summary.get("partial_failure"))
    fetch_notes = provenance.get("fetch_notes") if isinstance(provenance.get("fetch_notes"), list) else []
    state_errors = provenance.get("state_errors") if isinstance(provenance.get("state_errors"), list) else []
    low_confidence = provenance.get("low_confidence_labels")
    low_confidence_count = len(low_confidence) if isinstance(low_confidence, list) else 0

    if partial_failure or state_errors:
        level = "risk"
        label = "需复核"
        note = "存在上游部分失败或状态错误，结论需要结合详情复核。"
    elif unknown > 0 or fetch_notes:
        level = "warning"
        label = "部分缺失"
        note = "存在未知情感或抓取提示，部分引用证据不足。"
    else:
        level = "ok"
        label = "可靠"
        note = "未发现阻塞性失败，报告可作为当前数据快照阅读。"

    return {
        "level": level,
        "label": label,
        "note": note,
        "items": [
            {"label": "未知情感", "value": unknown},
            {"label": "抓取提示", "value": len(fetch_notes)},
            {"label": "状态错误", "value": len(state_errors)},
            {"label": "低置信作者", "value": low_confidence_count},
        ],
    }


def _render_year_fallback(year_trend: dict[str, object]) -> str:
    fallback = year_trend.get("fallback")
    if not isinstance(fallback, dict) or not fallback:
        return "<p class='muted chart-fallback'>暂无年份数据。</p>"
    return "<ul class='data-list chart-fallback'>" + "".join(
        f"<li><span>{year}</span><strong>{count}</strong></li>"
        for year, count in fallback.items()
    ) + "</ul>"


def _year_trend_note(year_trend: dict[str, int], summary: dict[str, object]) -> str:
    if len(year_trend) >= 2:
        return "展示施引文献按年份分布，用于判断影响是否持续扩散。"
    if len(year_trend) == 1:
        year, count = next(iter(year_trend.items()))
        return f"当前样本集中在 {year} 年，共 {count} 篇施引文献；不伪装成趋势图。"
    return f"当前 {summary.get('citation_count', 0)} 篇施引文献缺少年份信息。"


def _coerce_int_map(value: object) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    result = {}
    for key, raw_count in value.items():
        count = _as_int(raw_count)
        if count < 0:
            continue
        result[str(key)] = count
    return result


def _nonzero_items(items: dict[str, int]) -> list[tuple[str, int]]:
    return [
        (label, count)
        for label, count in sorted(items.items(), key=lambda item: (-item[1], item[0]))
        if count > 0
    ]


def _top_n_with_others(items: dict[str, int], limit: int) -> list[tuple[str, int]]:
    nonzero = _nonzero_items(items)
    if len(nonzero) <= limit:
        return nonzero
    top_items = nonzero[:limit]
    other_count = sum(count for _, count in nonzero[limit:])
    if other_count:
        top_items.append(("Others", other_count))
    return top_items


def _as_int(value: object) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


def _json_for_script(value: object) -> str:
    return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")


def _slugify(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-") or "report"
