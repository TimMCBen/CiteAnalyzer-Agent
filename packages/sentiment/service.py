from __future__ import annotations

from typing import Mapping, Optional, Sequence

from packages.citation_sources.models import CitingPaper
from packages.sentiment.classifier import classify_sentiment
from packages.sentiment.fulltext import select_text_source
from packages.sentiment.models import CitationContext, FullTextDocument, SentimentAnalysisResult, SentimentSummary
from packages.sentiment.reference_locator import locate_reference_context
from packages.shared.models import AnalysisState, TargetPaper


def analyze_citation_sentiments(
    target_paper: TargetPaper,
    citing_papers: Sequence[CitingPaper],
    fulltext_documents: Optional[Mapping[str, FullTextDocument]] = None,
) -> SentimentAnalysisResult:
    contexts: list[CitationContext] = []
    summary = SentimentSummary(total_candidates=len(citing_papers))

    for citing_paper in citing_papers:
        text_source = select_text_source(citing_paper, provided_documents=fulltext_documents)
        if text_source.text:
            summary.fulltext_available += 1
        else:
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

        reference_match = locate_reference_context(text_source.text, target_paper=target_paper)
        if reference_match.context_text:
            summary.context_found += 1
            label, classifier_note = classify_sentiment(reference_match.context_text)
            if label != "unknown":
                summary.classified_count += 1
            else:
                summary.unknown_count += 1
            evidence_note = f"{reference_match.evidence_note}; {classifier_note}"
        else:
            label = "unknown"
            evidence_note = reference_match.evidence_note
            summary.unknown_count += 1

        summary.label_counts[label] += 1
        contexts.append(
            CitationContext(
                citing_paper_id=citing_paper.canonical_id,
                sentiment_label=label,
                context_text=reference_match.context_text,
                mention_span=reference_match.mention_span,
                matched_target_reference=reference_match.matched_target_reference,
                evidence_note=evidence_note,
                text_source_type=text_source.source_type,
                text_source_label=text_source.source_label,
            )
        )

    return SentimentAnalysisResult(contexts=contexts, summary=summary)


def attach_sentiment_result_to_state(state: AnalysisState, result: SentimentAnalysisResult) -> AnalysisState:
    state["citation_contexts"] = result.contexts  # type: ignore[assignment]
    state["sentiment_summary"] = result.summary  # type: ignore[assignment]
    state["status"] = "citation_sentiments_analyzed"
    return state
