from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class CitingPaper:
    canonical_id: str
    title: str
    doi: Optional[str] = None
    year: Optional[int] = None
    authors: List[str] = field(default_factory=list)
    venue: Optional[str] = None
    abstract: Optional[str] = None
    source_links: Dict[str, str] = field(default_factory=dict)
    source_names: List[str] = field(default_factory=list)
    source_specific_ids: Dict[str, str] = field(default_factory=dict)


@dataclass
class SourceTrace:
    candidate_id: str
    source_name: str
    source_record_id: str
    query_used: str
    fetched_at: str
    raw_title: Optional[str] = None
    raw_doi: Optional[str] = None
    merge_status: str = "unique"


@dataclass
class FetchSummary:
    target_query: str
    semantic_scholar_candidates: int = 0
    crossref_candidates: int = 0
    merged_candidates: int = 0
    deduped_candidates: int = 0
    partial_failure: bool = False
    notes: List[str] = field(default_factory=list)


@dataclass
class CitationFetchResult:
    citing_papers: List[CitingPaper] = field(default_factory=list)
    source_trace: List[SourceTrace] = field(default_factory=list)
    fetch_summary: FetchSummary = field(default_factory=lambda: FetchSummary(target_query=""))
    errors: List[str] = field(default_factory=list)
