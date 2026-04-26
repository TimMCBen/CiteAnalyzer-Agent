from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional, Tuple


SentimentLabel = Literal["positive", "neutral", "critical", "unknown"]


@dataclass
class FullTextDocument:
    citing_paper_id: str
    text: str
    source_type: Literal["fulltext", "markdown", "latex", "html", "pdf", "abstract", "unknown"] = "unknown"
    source_label: Optional[str] = None
    local_path: Optional[str] = None
    raw_path: Optional[str] = None
    extracted_dir: Optional[str] = None


@dataclass
class TextSourceSelection:
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
    matched_target_reference: Optional[str]
    context_text: Optional[str]
    mention_span: Optional[Tuple[int, int]]
    evidence_note: str


@dataclass
class CitationContext:
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
    contexts: List[CitationContext] = field(default_factory=list)
    summary: SentimentSummary = field(default_factory=SentimentSummary)
