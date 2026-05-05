from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Iterable

from packages.citation_sources.models import CitingPaper, FetchSummary, SourceTrace
from packages.sentiment.models import CitationContext, SentimentSummary
from packages.shared.models import AnalysisState, AuthorProfile, AuthorSummary, ReportArtifact, ScholarLabel, TargetPaper


DEFAULT_REPORT_DIR = Path("generated-reports")


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
            f"<li><span>{key}</span><strong>{value}</strong></li>"
            for key, value in items.items()
        )

    contexts_html = "".join(
        (
            "<article class='context-card'>"
            f"<div class='context-head'><h3>{context.citing_paper_id}</h3><span class='sentiment-tag'>{context.sentiment_label}</span></div>"
            f"<p><strong>evidence:</strong> {context.evidence_note}</p>"
            f"<p>{context.context_text or 'No context available.'}</p>"
            "</article>"
        )
        for context in citation_contexts
    )

    summary_metrics = [
        ("Citations", summary.get("citation_count", 0)),
        ("Heavyweight", summary.get("heavyweight_candidates", 0)),
        ("High Impact", summary.get("high_impact_candidates", 0)),
        ("Unknown Sentiment", summary.get("unknown_sentiments", 0)),
    ]
    metric_cards = "".join(
        f"<article class='card stat-card'><span>{label}</span><strong>{value}</strong></article>"
        for label, value in summary_metrics
    )
    provenance_items = [
        f"Partial failure: {provenance.get('partial_failure', False)}",
        f"Source traces: {provenance.get('source_trace_count', 0)}",
    ]
    provenance_items.extend(str(note) for note in provenance.get("fetch_notes", []))
    provenance_items.extend(str(error) for error in provenance.get("state_errors", []))
    provenance_items.extend(
        f"{item.get('author_id')}: {item.get('label')}: {item.get('confidence_note')}"
        for item in provenance.get("low_confidence_labels", [])
        if isinstance(item, dict)
    )

    return f"""<!doctype html>
<html lang="zh">
<head>
  <meta charset="utf-8" />
  <title>CiteAnalyzer Report - {target_paper.title or 'Unknown Target'}</title>
  <style>
    :root {{
      --bg: #f4efe6;
      --panel: #fffaf2;
      --ink: #1f2937;
      --muted: #6b7280;
      --line: #dfd1ba;
      --accent: #9f4f2b;
      --accent-soft: #f3e0ce;
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
    .card {{ border: 1px solid var(--line); border-radius: 16px; padding: 1rem; background: rgba(255, 250, 242, 0.96); }}
    .stat-card span {{ display: block; color: var(--muted); font-size: 0.95rem; margin-bottom: 0.35rem; }}
    .stat-card strong {{ font-size: 1.85rem; color: var(--accent); }}
    .list-card ul, .attention-list, .finding-list, .data-list {{ padding-left: 1.2rem; margin: 0; }}
    .data-list li {{ display: flex; justify-content: space-between; gap: 1rem; padding: 0.2rem 0; }}
    .data-list span {{ color: var(--muted); }}
    .attention-list li {{ color: var(--accent); }}
    .context-list {{ border: 1px solid var(--line); border-radius: 18px; padding: 1.25rem; background: rgba(255, 250, 242, 0.92); }}
    .context-card {{ border-top: 1px solid var(--line); padding-top: 1rem; margin-top: 1rem; }}
    .context-card:first-child {{ border-top: 0; margin-top: 0; padding-top: 0; }}
    .context-head {{ display: flex; justify-content: space-between; align-items: baseline; gap: 1rem; }}
    .sentiment-tag {{ color: var(--accent); font-weight: 700; text-transform: capitalize; }}
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
    <a href="#findings">Findings</a>
    <a href="#quality">Quality</a>
    <a href="#attention">Attention</a>
    <a href="#contexts">Contexts</a>
  </nav>
  <section class="metric-grid" id="metrics">
    {metric_cards}
    <article class="card list-card"><h2>Year Trend</h2><ul class="data-list">{render_map(charts['year_trend'])}</ul></article>
    <article class="card list-card"><h2>Source Map</h2><ul class="data-list">{render_map(charts['source_map'])}</ul></article>
    <article class="card list-card"><h2>Scholar Distribution</h2><ul class="data-list">{render_map(charts['scholar_distribution'])}</ul></article>
    <article class="card list-card"><h2>Sentiment Distribution</h2><ul class="data-list">{render_map(charts['sentiment_distribution'])}</ul></article>
  </section>
  <section id="findings">
    <h2>Key Findings</h2>
    <ul class="finding-list">{render_list(list(summary.get('key_findings', [])), 'No findings generated')}</ul>
  </section>
  <section id="quality">
    <h2>Data Quality Notes</h2>
    <ul class="attention-list">{render_list(provenance_items, 'No quality warnings')}</ul>
  </section>
  <section id="attention">
    <h2>Manual Attention Items</h2>
    <ul class="attention-list">{render_list(list(summary.get('manual_attention_items', [])), 'No manual attention items')}</ul>
  </section>
  <section id="contexts">
    <h2>Citation Contexts</h2>
    <div class="context-list">{contexts_html or '<p>No contexts available.</p>'}</div>
  </section>
</body>
</html>
"""


def _slugify(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-") or "report"
