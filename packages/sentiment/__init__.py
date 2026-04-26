"""Stage5 fulltext acquisition plus stage6 citation sentiment analysis."""

from packages.sentiment.fulltext import fetch_fulltext_document, select_text_source
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
    "fetch_fulltext_document",
    "FullTextDocument",
    "locate_reference_context_with_llm",
    "select_text_source",
    "SentimentAnalysisResult",
    "SentimentSummary",
    "TextSourceSelection",
]
