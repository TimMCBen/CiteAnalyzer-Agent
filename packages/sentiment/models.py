"""Models helpers for citation sentiment analysis."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional, Tuple


SentimentLabel = Literal["positive", "neutral", "critical", "unknown"]


@dataclass
class FullTextDocument:
    """Store full text document information used by citation sentiment analysis."""
    citing_paper_id: str
    text: str
    source_type: Literal["fulltext", "markdown", "latex", "html", "pdf", "abstract", "unknown"] = "unknown"
    source_label: Optional[str] = None
    local_path: Optional[str] = None
    raw_path: Optional[str] = None
    extracted_dir: Optional[str] = None
    evidence_note: Optional[str] = None


@dataclass
class TextSourceSelection:
    """Store text source selection information used by citation sentiment analysis."""
    citing_paper_id: str
    text: Optional[str]
    source_type: Literal["fulltext", "markdown", "latex", "html", "pdf", "abstract", "unknown"] = "unknown"
    source_label: Optional[str] = None
    local_path: Optional[str] = None
    raw_path: Optional[str] = None
    extracted_dir: Optional[str] = None
    evidence_note: str = "no_text_available"


@dataclass
class ReferenceMatch:
    """Store reference match information used by citation sentiment analysis."""
    matched_target_reference: Optional[str]
    context_text: Optional[str]
    mention_span: Optional[Tuple[int, int]]
    evidence_note: str


@dataclass
class CitationContext:
    """Store citation context information used by citation sentiment analysis."""
    citing_paper_id: str
    sentiment_label: SentimentLabel
    context_text: Optional[str] = None
    mention_span: Optional[Tuple[int, int]] = None
    matched_target_reference: Optional[str] = None
    evidence_note: str = "unable_to_determine"
    text_source_type: Literal["fulltext", "markdown", "latex", "html", "pdf", "abstract", "unknown"] = "unknown"
    text_source_label: Optional[str] = None


@dataclass
class SentimentSummary:
    """Store sentiment summary information used by citation sentiment analysis."""
    total_candidates: int = 0
    fulltext_available: int = 0
    context_found: int = 0
    classified_count: int = 0
    unknown_count: int = 0
    label_counts: Dict[SentimentLabel, int] = field(
        default_factory=lambda: {
            "positive": 0,
            "neutral": 0,
            "critical": 0,
            "unknown": 0,
        }
    )


@dataclass
class SentimentAnalysisResult:
    """Store sentiment analysis result information used by citation sentiment analysis."""
    contexts: List[CitationContext] = field(default_factory=list)
    summary: SentimentSummary = field(default_factory=SentimentSummary)
