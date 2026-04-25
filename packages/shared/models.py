from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional, TypedDict


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


class AnalysisState(TypedDict, total=False):
    raw_query: str
    request_type: str
    analysis_goal: str
    constraints: Dict[str, str]
    target_paper: TargetPaper
    errors: List[str]
    status: str
