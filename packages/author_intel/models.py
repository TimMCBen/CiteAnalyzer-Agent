"""Result containers for author profile enrichment and scholar labeling."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from packages.shared.models import AuthorProfile, AuthorSummary, ScholarLabel


@dataclass
class AuthorIntelResult:
    """Bundle enriched author profiles, derived labels, summary counts, and errors."""
    author_profiles: List[AuthorProfile] = field(default_factory=list)
    scholar_labels: List[ScholarLabel] = field(default_factory=list)
    author_summary: AuthorSummary = field(default_factory=AuthorSummary)
    errors: List[str] = field(default_factory=list)
