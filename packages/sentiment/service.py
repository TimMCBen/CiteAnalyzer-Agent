"""Service layer that turns citing-paper texts into sentiment analysis results."""
from __future__ import annotations

from typing import Callable, Mapping, Optional, Sequence

from packages.citation_sources.models import CitingPaper
from packages.sentiment.classifier import classify_sentiment
from packages.sentiment.fulltext import select_text_source
from packages.sentiment.models import CitationContext, FullTextDocument, SentimentAnalysisResult, SentimentSummary
from packages.sentiment.workflow import run_stage6_workflow
from packages.shared.models import AnalysisState, TargetPaper
from packages.shared.runtime_logging import get_runtime_logger

VALID_SENTIMENT_LABELS = {"positive", "neutral", "critical", "unknown"}


def analyze_citation_sentiments(
    target_paper: TargetPaper,
    citing_papers: Sequence[CitingPaper],
    fulltext_documents: Optional[Mapping[str, FullTextDocument]] = None,
    allow_network: bool = True,
    search_arxiv_fallback: bool = True,
    use_llm_reference_fallback: bool = True,
    llm_reference_matcher: Optional[Callable[[str, TargetPaper], object]] = None,
) -> SentimentAnalysisResult:
    """Analyze all citing papers and summarize context coverage plus labels."""
    contexts: list[CitationContext] = []
    summary = SentimentSummary(total_candidates=len(citing_papers))

    for citing_paper in citing_papers:
        text_source = select_text_source(
            citing_paper,
            provided_documents=fulltext_documents,
            allow_network=allow_network,
            search_arxiv_fallback=search_arxiv_fallback,
        )
        if text_source.text and text_source.source_type != "abstract":
            summary.fulltext_available += 1
        if not text_source.text:
            get_runtime_logger().warn(
                "sentiment.unknown",
                "没有可用文本，无法判断引用情感",
                citing_paper_id=citing_paper.canonical_id,
                reason=text_source.evidence_note,
            )
            contexts.append(
                CitationContext(
                    citing_paper_id=citing_paper.canonical_id,
                    sentiment_label="unknown",
                    context_text=None,
                    mention_span=None,
                    matched_target_reference=None,
                    evidence_note=text_source.evidence_note,
                    text_source_type=text_source.source_type,
                    text_source_label=text_source.source_label,
                )
            )
            summary.unknown_count += 1
            summary.label_counts["unknown"] += 1
            continue
        if text_source.source_type == "abstract":
            get_runtime_logger().warn(
                "sentiment.unknown",
                "仅有摘要文本，无法可靠定位目标论文引用上下文",
                citing_paper_id=citing_paper.canonical_id,
                reason=text_source.evidence_note,
            )
            contexts.append(
                CitationContext(
                    citing_paper_id=citing_paper.canonical_id,
                    sentiment_label="unknown",
                    context_text=None,
                    mention_span=None,
                    matched_target_reference=None,
                    evidence_note=text_source.evidence_note,
                    text_source_type=text_source.source_type,
                    text_source_label=text_source.source_label,
                )
            )
            summary.unknown_count += 1
            summary.label_counts["unknown"] += 1
            continue

        if use_llm_reference_fallback:
            citation_context = run_stage6_workflow(
                target_paper=target_paper,
                citing_paper=citing_paper,
                text_source=text_source,
                llm_reference_matcher=llm_reference_matcher,
            )
        else:
            citation_context = run_stage6_workflow(
                target_paper=target_paper,
                citing_paper=citing_paper,
                text_source=text_source,
                llm_reference_matcher=None,
            )

        if citation_context.context_text:
            summary.context_found += 1
            get_runtime_logger().detail(
                "sentiment.context",
                "已找到引用上下文",
                citing_paper_id=citing_paper.canonical_id,
                source_type=citation_context.text_source_type,
            )
        if citation_context.sentiment_label not in VALID_SENTIMENT_LABELS:
            citation_context.sentiment_label = "unknown"
            citation_context.evidence_note = f"{citation_context.evidence_note}; invalid_label_normalized_to_unknown"
            get_runtime_logger().warn(
                "sentiment.unknown",
                "情感分类标签无效，已归一化为 unknown",
                citing_paper_id=citing_paper.canonical_id,
            )
        if citation_context.sentiment_label != "unknown":
            summary.classified_count += 1
        else:
            summary.unknown_count += 1
            get_runtime_logger().warn(
                "sentiment.unknown",
                "引用情感无法判断",
                citing_paper_id=citing_paper.canonical_id,
                reason=citation_context.evidence_note,
            )
        summary.label_counts[citation_context.sentiment_label] += 1
        contexts.append(citation_context)

    return SentimentAnalysisResult(contexts=contexts, summary=summary)


def attach_sentiment_result_to_state(state: AnalysisState, result: SentimentAnalysisResult) -> AnalysisState:
    """Store sentiment contexts and summary metrics on the analyzer state."""
    state["citation_contexts"] = result.contexts  # type: ignore[assignment]
    state["sentiment_summary"] = result.summary  # type: ignore[assignment]
    state["status"] = "citation_sentiments_analyzed"
    return state
