from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Iterable

from packages.citation_sources.models import CitingPaper
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
    output_dir: Path | None = None,
) -> ReportArtifact:
    report_id = target_paper.canonical_id or target_paper.doi or target_paper.title or "unknown-target"
    safe_report_id = _slugify(report_id)
    report_dir = (output_dir or DEFAULT_REPORT_DIR).resolve() / safe_report_id
    report_dir.mkdir(parents=True, exist_ok=True)

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
        "key_findings": _build_key_findings(citing_papers, scholar_labels, sentiment_summary),
        "manual_attention_items": _build_manual_attention_items(citation_contexts),
    }

    json_path = report_dir / "report.json"
    html_path = report_dir / "report.html"
    json_path.write_text(
        json.dumps(
            {
                "summary": summary,
                "charts": chart_payloads,
                "contexts": [_serialize_context(context) for context in citation_contexts],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    html_path.write_text(_render_html(target_paper, summary, chart_payloads, citation_contexts), encoding="utf-8")

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
) -> list[str]:
    findings = [
        f"共识别 {len(citing_papers)} 篇施引论文。",
        f"重量级学者候选 {sum(1 for label in scholar_labels if label.label == 'heavyweight_candidate')} 位。",
        f"已分类引用 {sentiment_summary.classified_count} 条，无法判断 {sentiment_summary.unknown_count} 条。",
    ]
    return findings


def _build_manual_attention_items(citation_contexts: Iterable[CitationContext]) -> list[str]:
    items = []
    for context in citation_contexts:
        if context.sentiment_label == "unknown":
            items.append(f"{context.citing_paper_id}: {context.evidence_note}")
    return items


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
    citation_contexts: list[CitationContext],
) -> str:
    def render_list(items: list[str]) -> str:
        if not items:
            return "<li>None</li>"
        return "".join(f"<li>{item}</li>" for item in items)

    contexts_html = "".join(
        (
            "<article class='context-card'>"
            f"<h3>{context.citing_paper_id}</h3>"
            f"<p><strong>sentiment:</strong> {context.sentiment_label}</p>"
            f"<p><strong>evidence:</strong> {context.evidence_note}</p>"
            f"<p>{context.context_text or 'No context available.'}</p>"
            "</article>"
        )
        for context in citation_contexts
    )

    return f"""<!doctype html>
<html lang="zh">
<head>
  <meta charset="utf-8" />
  <title>CiteAnalyzer Report - {target_paper.title or 'Unknown Target'}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 2rem; color: #1f2937; }}
    section {{ margin-bottom: 2rem; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 1rem; }}
    .card {{ border: 1px solid #d1d5db; border-radius: 12px; padding: 1rem; background: #f9fafb; }}
    .context-card {{ border-top: 1px solid #e5e7eb; padding-top: 1rem; margin-top: 1rem; }}
    pre {{ white-space: pre-wrap; word-break: break-word; }}
  </style>
</head>
<body>
  <section>
    <h1>{target_paper.title or 'Unknown Target Paper'}</h1>
    <p><strong>DOI:</strong> {target_paper.doi or 'N/A'}</p>
  </section>
  <section class="grid">
    <div class="card"><h2>Summary</h2><pre>{json.dumps(summary, ensure_ascii=False, indent=2)}</pre></div>
    <div class="card"><h2>Year Trend</h2><pre>{json.dumps(charts['year_trend'], ensure_ascii=False, indent=2)}</pre></div>
    <div class="card"><h2>Source Map</h2><pre>{json.dumps(charts['source_map'], ensure_ascii=False, indent=2)}</pre></div>
    <div class="card"><h2>Scholar Distribution</h2><pre>{json.dumps(charts['scholar_distribution'], ensure_ascii=False, indent=2)}</pre></div>
    <div class="card"><h2>Sentiment Distribution</h2><pre>{json.dumps(charts['sentiment_distribution'], ensure_ascii=False, indent=2)}</pre></div>
  </section>
  <section>
    <h2>Key Findings</h2>
    <ul>{render_list(list(summary.get('key_findings', [])))}</ul>
  </section>
  <section>
    <h2>Manual Attention Items</h2>
    <ul>{render_list(list(summary.get('manual_attention_items', [])))}</ul>
  </section>
  <section>
    <h2>Citation Contexts</h2>
    {contexts_html or '<p>No contexts available.</p>'}
  </section>
</body>
</html>
"""


def _slugify(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-") or "report"
