from __future__ import annotations

from typing import Callable, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from packages.citation_sources.models import CitingPaper
from packages.sentiment.classifier import classify_sentiment
from packages.sentiment.grobid_context import locate_reference_context_from_grobid_pdf
from packages.sentiment.llm_locator import (
    find_bibliography_match,
    find_body_context_for_citation_key,
    locate_reference_context_with_llm,
)
from packages.sentiment.models import CitationContext, ReferenceMatch, TextSourceSelection
from packages.sentiment.reference_locator import locate_reference_context
from packages.shared.models import TargetPaper

VALID_SENTIMENT_LABELS = {"positive", "neutral", "critical", "unknown"}


class Stage6PaperState(TypedDict, total=False):
    target_paper: TargetPaper
    citing_paper: CitingPaper
    text_source: TextSourceSelection
    is_tex_source: bool
    is_pdf_source: bool
    bibliography_reference: Optional[str]
    bibliography_key: Optional[str]
    bibliography_path: Optional[str]
    reference_match: ReferenceMatch
    grobid_note: str
    sentiment_label: str
    classifier_note: str
    citation_context: CitationContext


def run_stage6_workflow(
    target_paper: TargetPaper,
    citing_paper: CitingPaper,
    text_source: TextSourceSelection,
    llm_reference_matcher: Optional[Callable[..., object]] = None,
) -> CitationContext:
    matcher = llm_reference_matcher or locate_reference_context_with_llm

    def load_fulltext_artifact(state: Stage6PaperState) -> Stage6PaperState:
        return state

    def detect_source_kind(state: Stage6PaperState) -> Stage6PaperState:
        state["is_tex_source"] = state["text_source"].source_type == "latex" and bool(state["text_source"].extracted_dir)
        state["is_pdf_source"] = state["text_source"].source_type == "pdf" and bool(state["text_source"].raw_path)
        return state

    def grobid_pdf_context_matcher(state: Stage6PaperState) -> Stage6PaperState:
        if not state.get("is_pdf_source"):
            return state
        raw_path = state["text_source"].raw_path
        if not raw_path:
            return state
        try:
            grobid_match = locate_reference_context_from_grobid_pdf(
                pdf_path=__import__("pathlib").Path(raw_path),
                target_paper=state["target_paper"],
            )
        except Exception as exc:
            state["grobid_note"] = f"grobid_unavailable:{exc.__class__.__name__}"
            return state
        if grobid_match.context_text:
            state["reference_match"] = grobid_match
        return state

    def tex_bibliography_matcher(state: Stage6PaperState) -> Stage6PaperState:
        if state.get("reference_match") and state["reference_match"].context_text:
            return state
        if not state.get("is_tex_source"):
            return state
        extracted_dir = state["text_source"].extracted_dir
        if not extracted_dir:
            return state
        target = state["target_paper"]
        hit = find_bibliography_match(
            extracted_dir=__import__("pathlib").Path(extracted_dir),
            target_doi=(target.doi or "").lower(),
            target_title=(target.title or target.paper_query or "").lower(),
        )
        if hit is None:
            return state
        citation_key, bibliography_entry, bibliography_path = hit
        state["bibliography_key"] = citation_key
        state["bibliography_reference"] = bibliography_entry
        state["bibliography_path"] = str(bibliography_path)
        return state

    def body_citation_finder(state: Stage6PaperState) -> Stage6PaperState:
        if state.get("reference_match") and state["reference_match"].context_text:
            return state
        text_source_local = state["text_source"]
        target = state["target_paper"]

        if state.get("bibliography_key") and text_source_local.extracted_dir:
            context_hit = find_body_context_for_citation_key(
                extracted_dir=__import__("pathlib").Path(text_source_local.extracted_dir),
                citation_key=state["bibliography_key"] or "",
            )
            if context_hit is not None:
                context_text, source_path = context_hit
                state["reference_match"] = ReferenceMatch(
                    matched_target_reference=f"{state['bibliography_key']} @ {__import__('pathlib').Path(state['bibliography_path']).name}",
                    context_text=context_text,
                    mention_span=None,
                    evidence_note=f"matched_by_tex_bibliography_and_cite_key:{state['bibliography_key']} @ {source_path.name}",
                )
                return state

        llm_match = matcher(
            text_source_local.text or "",
            target,
            source_type=text_source_local.source_type,
            extracted_dir=text_source_local.extracted_dir,
        )
        if getattr(llm_match, "context_text", None):
            state["reference_match"] = llm_match  # type: ignore[assignment]
            return state

        state["reference_match"] = locate_reference_context(text_source_local.text or "", target_paper=target)
        return state

    def sentiment_classifier(state: Stage6PaperState) -> Stage6PaperState:
        reference_match = state["reference_match"]
        if not reference_match.context_text:
            state["sentiment_label"] = "unknown"
            state["classifier_note"] = append_grobid_note(reference_match.evidence_note, state.get("grobid_note"))
            return state

        try:
            label, classifier_note = classify_sentiment(reference_match.context_text, target_paper=state["target_paper"])
        except Exception as exc:
            state["sentiment_label"] = "unknown"
            state["classifier_note"] = append_grobid_note(
                f"{reference_match.evidence_note}; llm_sentiment_failed:{exc.__class__.__name__}",
                state.get("grobid_note"),
            )
            return state

        if label not in VALID_SENTIMENT_LABELS:
            label = "unknown"
            classifier_note = f"{classifier_note}; invalid_label_normalized_to_unknown"

        state["sentiment_label"] = label
        state["classifier_note"] = append_grobid_note(
            f"{reference_match.evidence_note}; {classifier_note}",
            state.get("grobid_note"),
        )
        return state

    def aggregate_output(state: Stage6PaperState) -> Stage6PaperState:
        reference_match = state["reference_match"]
        text_source_local = state["text_source"]
        state["citation_context"] = CitationContext(
            citing_paper_id=state["citing_paper"].canonical_id,
            sentiment_label=state["sentiment_label"],  # type: ignore[arg-type]
            context_text=reference_match.context_text,
            mention_span=reference_match.mention_span,
            matched_target_reference=reference_match.matched_target_reference,
            evidence_note=state["classifier_note"],
            text_source_type=text_source_local.source_type,
            text_source_label=text_source_local.source_label,
        )
        return state

    graph = StateGraph(Stage6PaperState)
    graph.add_node("load_fulltext_artifact", load_fulltext_artifact)
    graph.add_node("detect_source_kind", detect_source_kind)
    graph.add_node("grobid_pdf_context_matcher", grobid_pdf_context_matcher)
    graph.add_node("tex_bibliography_matcher", tex_bibliography_matcher)
    graph.add_node("body_citation_finder", body_citation_finder)
    graph.add_node("sentiment_classifier", sentiment_classifier)
    graph.add_node("aggregate_output", aggregate_output)

    graph.add_edge(START, "load_fulltext_artifact")
    graph.add_edge("load_fulltext_artifact", "detect_source_kind")
    graph.add_edge("detect_source_kind", "grobid_pdf_context_matcher")
    graph.add_edge("grobid_pdf_context_matcher", "tex_bibliography_matcher")
    graph.add_edge("tex_bibliography_matcher", "body_citation_finder")
    graph.add_edge("body_citation_finder", "sentiment_classifier")
    graph.add_edge("sentiment_classifier", "aggregate_output")
    graph.add_edge("aggregate_output", END)

    app = graph.compile()
    final_state = app.invoke(
        Stage6PaperState(
            target_paper=target_paper,
            citing_paper=citing_paper,
            text_source=text_source,
        )
    )
    return final_state["citation_context"]


def append_grobid_note(evidence_note: str, grobid_note: Optional[str]) -> str:
    if not grobid_note:
        return evidence_note
    return f"{evidence_note}; {grobid_note}"
