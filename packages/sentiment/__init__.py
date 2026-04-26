"""Stage5 fulltext acquisition plus stage6 citation sentiment analysis."""

from packages.sentiment.fulltext import fetch_fulltext_document, select_text_source
from packages.sentiment.grobid_client import grobid_is_alive, process_fulltext_document
from packages.sentiment.grobid_context import (
    extract_contexts_for_bibl_id,
    locate_reference_context_from_grobid_pdf,
    locate_reference_context_from_grobid_tei,
)
from packages.sentiment.models import (
    CitationContext,
    FullTextDocument,
    SentimentAnalysisResult,
    SentimentSummary,
    TextSourceSelection,
)
from packages.sentiment.service import analyze_citation_sentiments, attach_sentiment_result_to_state
from packages.sentiment.llm_locator import locate_reference_context_with_llm

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
