"""Models helpers for paper identity matching."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


ArxivStatus = Literal[
    "absent",
    "present_unchecked",
    "present_verified",
    "present_title_variant",
    "present_mismatch",
    "title_search_hit",
    "title_search_miss",
    "lookup_failed",
]
DOIStatus = Literal[
    "absent",
    "present_unchecked",
    "present_verified",
    "present_title_variant",
    "present_mismatch",
    "present_dead",
    "lookup_failed",
]
OpenAlexWorkStatus = Literal[
    "not_attempted",
    "doi_hit_verified",
    "doi_hit_variant",
    "doi_hit_mismatch",
    "title_hit_verified",
    "title_hit_variant",
    "title_hit_mismatch",
    "no_result",
    "lookup_failed",
]
SelectedWorkSource = Literal[
    "doi_verified",
    "arxiv_verified",
    "openalex_title_verified",
    "title_variant",
    "semantic_scholar_only",
    "conflicting_sources",
    "unresolved",
]
PaperMatchConfidence = Literal["high", "medium", "low", "miss", "error"]
AuthorResolutionStatus = Literal[
    "work_authorship_verified",
    "work_authorship_variant",
    "name_search_verified",
    "name_search_first_candidate",
    "weak_signal_only",
    "skipped_due_to_paper_mismatch",
    "lookup_failed",
]


@dataclass
class CandidateAuthor:
    """Store candidate author information used by paper identity matching."""
    name: str
    author_id: str | None = None
    orcid: str | None = None
    institutions: list[str] = field(default_factory=list)
    countries: list[str] = field(default_factory=list)
    raw_author_name: str | None = None


@dataclass
class CandidateWork:
    """Store candidate work information used by paper identity matching."""
    source: str
    work_id: str | None
    title: str
    doi: str | None = None
    year: int | None = None
    work_type: str | None = None
    url: str | None = None
    pdf_url: str | None = None
    arxiv_id: str | None = None
    authors: list[CandidateAuthor] = field(default_factory=list)

    @property
    def author_ids(self) -> list[str]:
        return [author.author_id for author in self.authors if author.author_id]


@dataclass
class PaperIdentityEvidence:
    """Store paper identity evidence information used by paper identity matching."""
    citing_paper_id: str
    title: str
    doi: str | None = None
    year: int | None = None
    authors: list[str] = field(default_factory=list)
    arxiv_id_hints: list[str] = field(default_factory=list)
    doi_work: CandidateWork | None = None
    title_work_candidates: list[CandidateWork] = field(default_factory=list)
    arxiv_candidates: list[CandidateWork] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class LLMIdentityReview:
    """Store LLM identity review information used by paper identity matching."""
    paper_identity_decision: Literal["same_paper", "different_paper", "uncertain"] = "uncertain"
    paper_confidence: PaperMatchConfidence = "medium"
    selected_source: str = "none"
    doi_assessment: str = "unverified"
    arxiv_assessment: str = "unverified"
    openalex_work_assessment: str = "unverified"
    author_resolution_decision: str = "manual_review"
    author_confidence: str = "unknown"
    risk_flags: list[str] = field(default_factory=list)
    needs_manual_review: bool = True
    reason_zh: str = ""


@dataclass
class PaperIdentityDecision:
    """Store paper identity decision information used by paper identity matching."""
    citing_paper_id: str
    arxiv_status: ArxivStatus
    doi_status: DOIStatus
    openalex_work_status: OpenAlexWorkStatus
    selected_work_source: SelectedWorkSource
    paper_match_confidence: PaperMatchConfidence
    author_resolution_status: AuthorResolutionStatus
    selected_work: CandidateWork | None = None
    title_similarity: float | None = None
    source_conflicts: list[str] = field(default_factory=list)
    evidence_notes: list[str] = field(default_factory=list)
    needs_llm_review: bool = False
    llm_review: LLMIdentityReview | None = None

    def to_log_dict(self) -> dict[str, object]:
        return {
            "citing_paper_id": self.citing_paper_id,
            "arxiv_status": self.arxiv_status,
            "doi_status": self.doi_status,
            "openalex_work_status": self.openalex_work_status,
            "selected_work_source": self.selected_work_source,
            "paper_match_confidence": self.paper_match_confidence,
            "author_resolution_status": self.author_resolution_status,
            "selected_work_id": self.selected_work.work_id if self.selected_work else None,
            "selected_work_title": self.selected_work.title if self.selected_work else None,
            "title_similarity": self.title_similarity,
            "source_conflicts": list(self.source_conflicts),
            "evidence_notes": list(self.evidence_notes),
            "needs_llm_review": self.needs_llm_review,
            "llm_reason_zh": self.llm_review.reason_zh if self.llm_review else None,
        }
