from __future__ import annotations

from packages.paper_identity.models import (
    ArxivStatus,
    AuthorResolutionStatus,
    CandidateWork,
    DOIStatus,
    OpenAlexWorkStatus,
    PaperIdentityDecision,
    PaperIdentityEvidence,
    PaperMatchConfidence,
    SelectedWorkSource,
)
from packages.paper_identity.service import resolve_paper_identity, resolve_paper_identities

__all__ = [
    "ArxivStatus",
    "AuthorResolutionStatus",
    "CandidateWork",
    "DOIStatus",
    "OpenAlexWorkStatus",
    "PaperIdentityDecision",
    "PaperIdentityEvidence",
    "PaperMatchConfidence",
    "SelectedWorkSource",
    "resolve_paper_identity",
    "resolve_paper_identities",
]
