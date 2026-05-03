from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional, TypedDict


@dataclass
class UserQuery:
    raw_text: str
    language: str = "zh"
    request_id: Optional[str] = None


@dataclass
class TargetPaper:
    canonical_id: Optional[str] = None
    paper_query: Optional[str] = None
    paper_query_type: Literal["doi", "paper_id", "arxiv", "title", "unknown"] = "unknown"
    title: Optional[str] = None
    doi: Optional[str] = None
    source_ids: Dict[str, str] = field(default_factory=dict)
    resolve_status: Literal["resolved", "uncertain", "unresolved"] = "unresolved"

    def to_dict(self) -> Dict[str, object]:
        return {
            "canonical_id": self.canonical_id,
            "paper_query": self.paper_query,
            "paper_query_type": self.paper_query_type,
            "title": self.title,
            "doi": self.doi,
            "source_ids": dict(self.source_ids),
            "resolve_status": self.resolve_status,
        }


@dataclass
class ParsedUserIntent:
    request_type: Literal["citation_analysis", "unsupported"] = "unsupported"
    paper_query: Optional[str] = None
    paper_query_type: Literal["doi", "paper_id", "arxiv", "title", "unknown"] = "unknown"
    analysis_goal: Optional[str] = None
    constraints: Dict[str, str] = field(default_factory=dict)
    reason: Optional[str] = None


@dataclass
class AuthorProfile:
    author_id: str
    name: str
    source_ids: Dict[str, str] = field(default_factory=dict)
    affiliations: List[str] = field(default_factory=list)
    fields: List[str] = field(default_factory=list)
    h_index: Optional[int] = None
    citation_count: Optional[int] = None
    works_count: Optional[int] = None
    evidence_sources: List[str] = field(default_factory=list)


@dataclass
class ScholarLabel:
    author_id: str
    label: Literal["high_impact_candidate", "heavyweight_candidate", "weak_signal_candidate"]
    evidence: List[str] = field(default_factory=list)
    confidence_note: Optional[str] = None
    trigger_rules: List[str] = field(default_factory=list)


@dataclass
class AuthorSummary:
    total_authors: int = 0
    matched_profiles: int = 0
    high_impact_candidates: int = 0
    heavyweight_candidates: int = 0
    weak_signal_candidates: int = 0


@dataclass
class ReportArtifact:
    report_id: str
    target_paper_id: str
    summary: Dict[str, object] = field(default_factory=dict)
    charts: Dict[str, object] = field(default_factory=dict)
    export_paths: Dict[str, str] = field(default_factory=dict)


class AnalysisState(TypedDict, total=False):
    raw_query: str
    request_type: str
    analysis_goal: str
    constraints: Dict[str, str]
    target_paper: TargetPaper
    citing_papers: List[Any]
    source_trace: List[Any]
    fetch_summary: Any
    fulltext_documents: Dict[str, Any]
    author_profiles: List[AuthorProfile]
    scholar_labels: List[ScholarLabel]
    author_summary: AuthorSummary
    citation_contexts: List[Any]
    sentiment_summary: Any
    report_artifact: ReportArtifact
    errors: List[str]
    status: str
