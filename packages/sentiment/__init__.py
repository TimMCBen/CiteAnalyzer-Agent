"""Stage5 fulltext acquisition plus stage6 citation sentiment analysis."""

from packages.sentiment.models import (
    CitationContext,
    FullTextDocument,
    SentimentAnalysisResult,
    SentimentSummary,
    TextSourceSelection,
)

__all__ = [
    "analyze_citation_sentiments",
    "attach_sentiment_result_to_state",
    "CitationContext",
    "extract_contexts_for_bibl_id",
    "fetch_fulltext_document",
    "FullTextDocument",
    "grobid_is_alive",
    "locate_reference_context_from_grobid_pdf",
    "locate_reference_context_from_grobid_tei",
    "locate_reference_context_with_llm",
    "process_fulltext_document",
    "select_text_source",
    "SentimentAnalysisResult",
    "SentimentSummary",
    "TextSourceSelection",
]


def __getattr__(name: str):
    """Lazily expose sentiment helpers without forcing optional imports at package load."""
    if name in {"fetch_fulltext_document", "select_text_source"}:
        from packages.sentiment.fulltext import fetch_fulltext_document, select_text_source

        return {
            "fetch_fulltext_document": fetch_fulltext_document,
            "select_text_source": select_text_source,
        }[name]

    if name in {"grobid_is_alive", "process_fulltext_document"}:
        from packages.sentiment.grobid_client import grobid_is_alive, process_fulltext_document

        return {
            "grobid_is_alive": grobid_is_alive,
            "process_fulltext_document": process_fulltext_document,
        }[name]

    if name in {
        "extract_contexts_for_bibl_id",
        "locate_reference_context_from_grobid_pdf",
        "locate_reference_context_from_grobid_tei",
    }:
        from packages.sentiment.grobid_context import (
            extract_contexts_for_bibl_id,
            locate_reference_context_from_grobid_pdf,
            locate_reference_context_from_grobid_tei,
        )

        return {
            "extract_contexts_for_bibl_id": extract_contexts_for_bibl_id,
            "locate_reference_context_from_grobid_pdf": locate_reference_context_from_grobid_pdf,
            "locate_reference_context_from_grobid_tei": locate_reference_context_from_grobid_tei,
        }[name]

    if name in {"analyze_citation_sentiments", "attach_sentiment_result_to_state"}:
        from packages.sentiment.service import analyze_citation_sentiments, attach_sentiment_result_to_state

        return {
            "analyze_citation_sentiments": analyze_citation_sentiments,
            "attach_sentiment_result_to_state": attach_sentiment_result_to_state,
        }[name]

    if name == "locate_reference_context_with_llm":
        from packages.sentiment.llm_locator import locate_reference_context_with_llm

        return locate_reference_context_with_llm

    raise AttributeError(f"module 'packages.sentiment' has no attribute {name!r}")
